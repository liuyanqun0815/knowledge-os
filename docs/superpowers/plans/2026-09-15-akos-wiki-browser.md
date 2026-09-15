# Wiki Browser UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a read-only Wiki browser page with left/right layout, Obsidian-style page links, and full-corpus keyword search with highlight.

**Architecture:** Backend GET APIs read compiled wiki under `{data_root}/kb/{kb_id}/wiki/` via `load_pages_meta` + safe path resolve. Frontend `/wiki` uses `KbContext`, renders a hub tree / search hits on the left and Markdown on the right; `[[folder/slug|label]]` navigates when the target exists in the tree; search query `q` highlights text.

**Tech Stack:** FastAPI, pydantic schemas, pytest; React 18, React Router 6, `react-markdown` + `remark-gfm`, Vitest, Testing Library.

## Global Constraints

- Data source: compile layer only (`wiki.paths.compile_wiki_root`), never export path
- Read-only: no wiki write/edit endpoints in this plan
- Wikilink jump: only when `page_id` exists in tree; `source-` / `chunk-` / fake entity links do not navigate
- Search: case-insensitive substring on title, summary, body; empty `q` → empty hits; default `limit=50`, max `100`
- Path traversal on `page_id` must 400/404
- Do not enable `rehype-raw` (no raw HTML XSS surface)
- Follow existing admin auth (`require_admin_token` / `_resolve_active_kb`) and `apiFetch` patterns

---

## File Map

| File | Responsibility |
|------|----------------|
| `wiki/browser.py` | Pure helpers: resolve page path, build tree, search pages, extract snippets |
| `admin_api/schemas.py` | Response models for tree/page/search |
| `admin_api/routes_wiki.py` | GET endpoints |
| `tests/test_wiki_browser.py` | Unit tests for `wiki/browser.py` |
| `tests/test_admin_wiki_browser_api.py` | API tests |
| `web/src/api/wiki.ts` | Client: tree/page/search |
| `web/src/api/types.ts` | Shared TS types if needed |
| `web/src/components/WikiMarkdown.tsx` | Markdown + wikilink + highlight |
| `web/src/components/WikiSidebar.tsx` | Tree + search results |
| `web/src/pages/WikiPage.tsx` | Page shell, URL sync, data loading |
| `web/src/app/router.tsx` | `/wiki` route |
| `web/src/components/TopNav.tsx` | Nav item |
| `web/src/styles/global.css` | Wiki layout + `mark` styles |
| `web/package.json` | Add `react-markdown`, `remark-gfm` |

---

### Task 1: Wiki browser pure helpers

**Files:**
- Create: `wiki/browser.py`
- Test: `tests/test_wiki_browser.py`

**Interfaces:**
- Produces:
  - `resolve_wiki_page_path(wiki_root: Path, page_id: str) -> Path`
  - `build_wiki_tree(wiki_root: Path) -> dict`
  - `read_wiki_page(wiki_root: Path, page_id: str) -> dict`
  - `search_wiki_pages(wiki_root: Path, query: str, *, limit: int = 50) -> dict`

- [ ] **Step 1: Write failing unit tests**

```python
# tests/test_wiki_browser.py
from pathlib import Path
from wiki.meta import WikiPageMeta, save_pages_meta


def _seed(wiki: Path) -> None:
    (wiki / "售后").mkdir(parents=True)
    (wiki / "售后" / "七天无理由退货.md").write_text(
        "# 七天\n\n## 摘要\n\n退款说明在此。\n", encoding="utf-8"
    )
    (wiki / "index.md").write_text(
        "---\nkb_id: kb1\n---\n\n## 主题\n\n### 售后\n> 涵盖七天无理由退货。\n"
        "- [[售后/七天无理由退货|七天无理由退货]] — 退款说明在此。\n",
        encoding="utf-8",
    )
    save_pages_meta(
        wiki,
        {
            "售后/七天无理由退货": WikiPageMeta(
                path="售后/七天无理由退货.md",
                title="七天无理由退货",
                kind="source_page",
                content_hash="h",
                source_ids=["s1"],
                hub="售后",
                summary="退款说明在此。",
            )
        },
    )


def test_resolve_rejects_traversal(tmp_path: Path):
    from wiki.browser import resolve_wiki_page_path
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    try:
        resolve_wiki_page_path(wiki, "../secrets")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_build_tree_groups_by_hub(tmp_path: Path):
    from wiki.browser import build_wiki_tree
    wiki = tmp_path / "wiki"
    _seed(wiki)
    tree = build_wiki_tree(wiki)
    assert tree["hubs"][0]["name"] == "售后"
    assert tree["hubs"][0]["pages"][0]["page_id"] == "售后/七天无理由退货"


def test_search_matches_body_snippet(tmp_path: Path):
    from wiki.browser import search_wiki_pages
    wiki = tmp_path / "wiki"
    _seed(wiki)
    result = search_wiki_pages(wiki, "退款")
    assert result["total"] >= 1
    assert result["hits"][0]["page_id"] == "售后/七天无理由退货"
    assert any("退款" in s for s in result["hits"][0]["snippets"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_wiki_browser.py -q`  
Expected: FAIL (import / not found)

- [ ] **Step 3: Implement `wiki/browser.py`**

```python
# wiki/browser.py — key behaviors
from pathlib import Path
from wiki.meta import load_pages_meta

def resolve_wiki_page_path(wiki_root: Path, page_id: str) -> Path:
    root = wiki_root.resolve()
    raw = "index.md" if page_id in {"", "index"} else f"{page_id}.md"
    target = (root / raw).resolve()
    if not str(target).startswith(str(root)):
        raise ValueError("path_escape")
    if not target.is_file():
        raise FileNotFoundError(page_id)
    return target

def build_wiki_tree(wiki_root: Path) -> dict:
    # group pages_meta by hub/folder; attach index.md hub descriptions when present
    ...

def read_wiki_page(wiki_root: Path, page_id: str) -> dict:
    path = resolve_wiki_page_path(wiki_root, page_id)
    markdown = path.read_text(encoding="utf-8")
    meta = load_pages_meta(wiki_root).get(page_id)
    title = meta.title if meta else path.stem
    return {"page_id": page_id if page_id else "index", "title": title, "path": str(path.relative_to(wiki_root)).replace("\\\\", "/"), "markdown": markdown}

def search_wiki_pages(wiki_root: Path, query: str, *, limit: int = 50) -> dict:
    # casefold substring on title/summary/body; snippets ±40 chars; rank title>summary>body
    ...
```

Also parse hub descriptions from `index.md` lines matching `### {hub}` followed by `> ...`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_wiki_browser.py -q`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add wiki/browser.py tests/test_wiki_browser.py
git commit -m "feat: add wiki browser pure helpers for tree/page/search"
```

---

### Task 2: Admin GET APIs + schemas

**Files:**
- Modify: `admin_api/schemas.py` (append after `WikiCompileResponse`)
- Modify: `admin_api/routes_wiki.py`
- Test: `tests/test_admin_wiki_browser_api.py`

**Interfaces:**
- Consumes: `build_wiki_tree`, `read_wiki_page`, `search_wiki_pages`, `compile_wiki_root`
- Produces: GET endpoints under `/admin/knowledge-bases/{kb_id}/wiki/...`

- [ ] **Step 1: Write failing API tests**

```python
# tests/test_admin_wiki_browser_api.py
from fastapi.testclient import TestClient
from app.main import create_app
from wiki.meta import WikiPageMeta, save_pages_meta
from wiki.paths import compile_wiki_root


def test_wiki_tree_and_page_and_search(tmp_path, monkeypatch):
    monkeypatch.delenv("ADMIN_API_TOKEN", raising=False)
    monkeypatch.setenv("AKOS_USE_PG", "false")
    client = TestClient(create_app(data_root=str(tmp_path)))
    kb_id = "legacy"
    wiki = compile_wiki_root(tmp_path, kb_id)
    (wiki / "售后").mkdir(parents=True)
    (wiki / "售后" / "退款到账时效.md").write_text("# 退款\n\n退款时效说明\n", encoding="utf-8")
    save_pages_meta(wiki, {
        "售后/退款到账时效": WikiPageMeta(
            path="售后/退款到账时效.md", title="退款到账时效", kind="source_page",
            content_hash="x", source_ids=["s"], hub="售后", summary="退款时效说明",
        )
    })

    tree = client.get(f"/admin/knowledge-bases/{kb_id}/wiki/tree")
    assert tree.status_code == 200
    assert tree.json()["hubs"][0]["pages"][0]["page_id"] == "售后/退款到账时效"

    page = client.get(f"/admin/knowledge-bases/{kb_id}/wiki/pages/售后/退款到账时效")
    assert page.status_code == 200
    assert "退款时效说明" in page.json()["markdown"]

    search = client.get(f"/admin/knowledge-bases/{kb_id}/wiki/search", params={"q": "退款"})
    assert search.status_code == 200
    assert search.json()["total"] >= 1

    bad = client.get(f"/admin/knowledge-bases/{kb_id}/wiki/pages/../secrets")
    assert bad.status_code in {400, 404}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_admin_wiki_browser_api.py -q`  
Expected: FAIL 404 on routes

- [ ] **Step 3: Add schemas**

```python
class WikiTreePageItem(BaseModel):
    page_id: str
    title: str
    summary: str | None = None

class WikiTreeHubItem(BaseModel):
    name: str
    description: str | None = None
    pages: list[WikiTreePageItem] = Field(default_factory=list)

class WikiTreeResponse(BaseModel):
    kb_id: str
    wiki_root: str
    hubs: list[WikiTreeHubItem] = Field(default_factory=list)

class WikiPageResponse(BaseModel):
    page_id: str
    title: str
    path: str
    markdown: str

class WikiSearchHit(BaseModel):
    page_id: str
    title: str
    snippets: list[str] = Field(default_factory=list)

class WikiSearchResponse(BaseModel):
    query: str
    total: int
    hits: list[WikiSearchHit] = Field(default_factory=list)
```

- [ ] **Step 4: Add GET routes in `routes_wiki.py`**

```python
@router.get("/{kb_id}/wiki/tree", response_model=WikiTreeResponse)
def get_wiki_tree(kb_id: str, request: Request, _: None = Depends(_resolve_active_kb)):
    settings = request.app.state.settings
    wiki_root = compile_wiki_root(settings.data_root, kb_id)
    if not wiki_root.is_dir():
        return WikiTreeResponse(kb_id=kb_id, wiki_root=str(wiki_root), hubs=[])
    payload = build_wiki_tree(wiki_root)
    return WikiTreeResponse(kb_id=kb_id, wiki_root=str(wiki_root), hubs=payload["hubs"])

@router.get("/{kb_id}/wiki/pages/{page_id:path}", response_model=WikiPageResponse)
def get_wiki_page(...):
    try:
        payload = read_wiki_page(wiki_root, page_id)
    except ValueError:
        raise HTTPException(400, detail="invalid_page_id")
    except FileNotFoundError:
        raise HTTPException(404, detail="wiki_page_not_found")
    return WikiPageResponse(**payload)

@router.get("/{kb_id}/wiki/search", response_model=WikiSearchResponse)
def search_wiki(kb_id: str, q: str = Query(""), limit: int = Query(50, ge=1, le=100), ...):
    ...
```

- [ ] **Step 5: Run API tests**

Run: `pytest tests/test_admin_wiki_browser_api.py tests/test_wiki_browser.py -q`  
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add admin_api/schemas.py admin_api/routes_wiki.py tests/test_admin_wiki_browser_api.py
git commit -m "feat: add wiki tree/page/search admin GET APIs"
```

---

### Task 3: Frontend API client

**Files:**
- Modify: `web/src/api/wiki.ts`
- Test: `web/src/api/wiki.test.ts` (create; mock `apiFetch` if project already mocks HTTP — otherwise skip unit test and cover via page tests in Task 5)

**Interfaces:**
- Produces:
  - `fetchWikiTree(kbId: string): Promise<WikiTreeResponse>`
  - `fetchWikiPage(kbId: string, pageId: string): Promise<WikiPageResponse>`
  - `searchWiki(kbId: string, q: string, limit?: number): Promise<WikiSearchResponse>`

- [ ] **Step 1: Extend `web/src/api/wiki.ts` with types + fetchers**

```typescript
export type WikiTreePageItem = { page_id: string; title: string; summary?: string | null };
export type WikiTreeHubItem = { name: string; description?: string | null; pages: WikiTreePageItem[] };
export type WikiTreeResponse = { kb_id: string; wiki_root: string; hubs: WikiTreeHubItem[] };
export type WikiPageResponse = { page_id: string; title: string; path: string; markdown: string };
export type WikiSearchHit = { page_id: string; title: string; snippets: string[] };
export type WikiSearchResponse = { query: string; total: number; hits: WikiSearchHit[] };

export async function fetchWikiTree(kbId: string): Promise<WikiTreeResponse> {
  const response = await apiFetch(`/admin/knowledge-bases/${kbId}/wiki/tree`);
  return response.json();
}

export async function fetchWikiPage(kbId: string, pageId: string): Promise<WikiPageResponse> {
  const encoded = pageId.split("/").map(encodeURIComponent).join("/");
  const response = await apiFetch(`/admin/knowledge-bases/${kbId}/wiki/pages/${encoded}`);
  return response.json();
}

export async function searchWiki(kbId: string, q: string, limit = 50): Promise<WikiSearchResponse> {
  const params = new URLSearchParams({ q, limit: String(limit) });
  const response = await apiFetch(`/admin/knowledge-bases/${kbId}/wiki/search?${params}`);
  return response.json();
}
```

- [ ] **Step 2: Commit**

```bash
git add web/src/api/wiki.ts
git commit -m "feat: add wiki browse API client helpers"
```

---

### Task 4: WikiMarkdown (wikilink + highlight)

**Files:**
- Create: `web/src/components/WikiMarkdown.tsx`
- Create: `web/src/components/WikiMarkdown.test.tsx`
- Modify: `web/package.json` (add deps)

**Interfaces:**
- Consumes: `pageIds: Set<string>`, `highlightQuery?: string`, `onNavigate(pageId: string)`
- Produces: rendered markdown with clickable real wikilinks and `<mark>` highlights

- [ ] **Step 1: Install deps**

```bash
cd web && npm install react-markdown remark-gfm
```

- [ ] **Step 2: Write failing component test**

```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { WikiMarkdown } from "./WikiMarkdown";

it("navigates real wikilinks and ignores fake entity links", async () => {
  const user = userEvent.setup();
  const onNavigate = vi.fn();
  render(
    <WikiMarkdown
      markdown={"参见 [[售后/退换货流程|退换货流程]] 与 [[女装尺码L|女装尺码L]]。"}
      pageIds={new Set(["售后/退换货流程"])}
      onNavigate={onNavigate}
    />,
  );
  await user.click(screen.getByRole("link", { name: "退换货流程" }));
  expect(onNavigate).toHaveBeenCalledWith("售后/退换货流程");
  expect(screen.queryByRole("link", { name: "女装尺码L" })).not.toBeInTheDocument();
});

it("highlights query terms", () => {
  render(
    <WikiMarkdown markdown={"退款将在三个工作日内到账"} pageIds={new Set()} highlightQuery="退款" />,
  );
  expect(screen.getByText("退款").tagName).toBe("MARK");
});
```

- [ ] **Step 3: Implement `WikiMarkdown.tsx`**

Parse text nodes for `[[target|label]]` / `[[target]]`:
- if `target` in `pageIds` → `<button className="wiki-wikilink">` or `<a role="link">` calling `onNavigate`
- else → plain text `label || target`
- if `highlightQuery`, wrap case-insensitive matches in `<mark>`
- Use `ReactMarkdown` + `remarkGfm`; custom `text` / paragraph children transformer for wikilink + highlight

- [ ] **Step 4: Run test**

Run: `cd web && npx vitest run src/components/WikiMarkdown.test.tsx`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add web/package.json web/package-lock.json web/src/components/WikiMarkdown.tsx web/src/components/WikiMarkdown.test.tsx
git commit -m "feat: render wiki markdown with wikilinks and highlight"
```

---

### Task 5: Wiki page shell, sidebar, routing, nav

**Files:**
- Create: `web/src/pages/WikiPage.tsx`
- Create: `web/src/pages/WikiPage.test.tsx`
- Create: `web/src/components/WikiSidebar.tsx`
- Modify: `web/src/app/router.tsx`
- Modify: `web/src/components/TopNav.tsx`
- Modify: `web/src/styles/global.css`

**Interfaces:**
- Consumes: `useKb()`, `fetchWikiTree`, `fetchWikiPage`, `searchWiki`, `WikiMarkdown`
- URL: `/wiki?kb=&page=&q=`

- [ ] **Step 1: Write failing page test (mock API)**

```tsx
vi.mock("../api/wiki", () => ({
  fetchWikiTree: vi.fn(async () => ({
    kb_id: "kb1",
    wiki_root: "/tmp",
    hubs: [{ name: "售后", description: "涵盖退货", pages: [
      { page_id: "售后/七天无理由退货", title: "七天无理由退货", summary: "退货政策" },
    ]}],
  })),
  fetchWikiPage: vi.fn(async () => ({
    page_id: "售后/七天无理由退货",
    title: "七天无理由退货",
    path: "售后/七天无理由退货.md",
    markdown: "# 七天\n\n可申请退款。\n",
  })),
  searchWiki: vi.fn(async () => ({ query: "退款", total: 1, hits: [
    { page_id: "售后/七天无理由退货", title: "七天无理由退货", snippets: ["可申请退款"] },
  ]})),
}));

it("renders tree and page content", async () => {
  render(/* WikiPage inside MemoryRouter + KbProvider with kb=kb1 */);
  expect(await screen.findByText("七天无理由退货")).toBeInTheDocument();
  expect(await screen.findByText(/可申请退款/)).toBeInTheDocument();
});
```

Follow existing page test patterns (`AskPage.test.tsx` / `KbProvider` helpers) for wrapping.

- [ ] **Step 2: Implement `WikiSidebar` + `WikiPage`**

`WikiPage` behavior:
1. If no `selectedKbId` → EmptyState「请先选择知识库」
2. Load tree on kb change; if `page` missing, open `index` if returned by API else first page in first hub
3. Left: hubs collapsed/expandable; click page → `setSearchParams({ page })`
4. When `q` present: call `searchWiki`, show hits list instead of (or above) tree; click hit opens page keeping `q`
5. Right: `WikiMarkdown` with `pageIds` from tree + `highlightQuery=q`
6. Loading / error banners reuse existing components

- [ ] **Step 3: Wire router + TopNav**

```tsx
// router.tsx
<Route path="/wiki" element={<WikiPage />} />

// TopNav.tsx
{ to: "/wiki", label: "Wiki" },
```

- [ ] **Step 4: CSS**

Add `.wiki-layout` (grid `280px 1fr`), `.wiki-search`, `.wiki-tree`, `.wiki-article`, `mark` background, `.wiki-wikilink` underline/color matching existing accents (no purple glow).

- [ ] **Step 5: Run frontend tests**

Run: `cd web && npx vitest run src/pages/WikiPage.test.tsx src/components/WikiMarkdown.test.tsx`  
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add web/src/pages/WikiPage.tsx web/src/pages/WikiPage.test.tsx web/src/components/WikiSidebar.tsx web/src/app/router.tsx web/src/components/TopNav.tsx web/src/styles/global.css
git commit -m "feat: add wiki browser page with tree and article pane"
```

---

### Task 6: Search UX polish + empty states

**Files:**
- Modify: `web/src/pages/WikiPage.tsx`
- Modify: `web/src/components/WikiSidebar.tsx`
- Modify: `web/src/pages/WikiPage.test.tsx`

- [ ] **Step 1: Extend tests**

```tsx
it("shows search hits and highlights query in article", async () => {
  const user = userEvent.setup();
  // render WikiPage
  await user.type(screen.getByPlaceholderText(/搜索|关键字/), "退款");
  await user.keyboard("{Enter}");
  expect(await screen.findByText(/命中/)).toBeInTheDocument();
  await user.click(screen.getByText("七天无理由退货"));
  expect(await screen.findByText("退款")).toBeVisible(); // marked
});

it("shows empty state when wiki has no hubs", async () => {
  // mock fetchWikiTree → hubs: []
  expect(await screen.findByText(/尚未编译|暂无 Wiki/)).toBeInTheDocument();
});
```

- [ ] **Step 2: Implement debounce or Enter-to-search** (prefer Enter + search button for simplicity; 300ms debounce optional)

- [ ] **Step 3: Clear query restores tree mode**

- [ ] **Step 4: Run tests**

Run: `cd web && npx vitest run src/pages/WikiPage.test.tsx`  
Expected: PASS

- [ ] **Step 5: Manual smoke**

1. Restart backend/frontend  
2. Open `/wiki` with KB that has compiled wiki  
3. Click tree → article updates  
4. Click `[[...]]` real link → navigates  
5. Search `退款` → hits → open → highlight  

- [ ] **Step 6: Commit**

```bash
git add web/src/pages/WikiPage.tsx web/src/pages/WikiPage.test.tsx web/src/components/WikiSidebar.tsx
git commit -m "feat: polish wiki full-corpus search and empty states"
```

---

## Spec Coverage Checklist

| Spec requirement | Task |
|------------------|------|
| Left/right layout | Task 5 |
| TopNav Wiki + `/wiki` | Task 5 |
| GET tree/page/search | Task 1–2 |
| Real wikilink navigation | Task 4–5 |
| Fake/source/chunk non-navigation | Task 4 |
| Full-corpus keyword search | Task 1–2, 6 |
| Highlight in article + snippets | Task 4, 6 |
| Path traversal safety | Task 1–2 |
| Empty states | Task 5–6 |
| Compile-layer only | Task 1–2 |
| No edit / no rehype-raw | Global + Task 4 |

---

## Self-Review Notes

- No TBD/placeholder steps remaining  
- Types aligned: `page_id` / `hubs` / `hits` / `snippets` shared across backend schemas and `wiki.ts`  
- Search ranking and snippet rules specified in Task 1  
- Frontend depends on Task 2 APIs; Markdown isolated in Task 4 before page shell  
