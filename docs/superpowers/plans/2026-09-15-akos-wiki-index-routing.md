# Wiki Index Routing Retrieval Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `WikiPageRetrieval` pseudo-BM25/hash search with keyword → `index.md` seed routing → existence-filtered 1-hop → weighted top-5 scoring → LLM path fallback.

**Architecture:** `extract_keywords` lives in `retrieval/wiki_keywords.py`. `WikiPageRetrieval` keeps only `wiki_root` + optional `llm_client`, reads files on demand, and returns existing `Hit` objects. Ask/bootstrap call sites stay the same except injecting `llm_client` at construction.

**Tech Stack:** Python 3.11+, jieba (with regex fallback), pathlib, existing `OpenAiCompatibleClient` / `StubLlmClient`, pytest.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-09-15-akos-wiki-index-routing-design.md` (confirmed)
- `index.md` never appears in hits; no page-body memory cache; no feature-flag back to hash search
- Skip immediately if invalid `wiki_root`, no leaf pages, or missing/unreadable `index.md`
- 1-hop only when seeds exist; only links whose `wiki_root/{target}.md` exists; skip `source-`/`chunk-`
- Wiki returns at most 5 hits: `top_k = min(requested, 5)`
- Keyword count mode: **substring** — each keyword contributes 1 if it appears in the haystack (case-sensitive for CJK; lowercasing optional only for ASCII)
- black `max_line_length=120`; no `from module import *`; TDD; commit per task; stage **only** task files

## File map

| File | Responsibility |
|------|----------------|
| `retrieval/wiki_keywords.py` | `extract_keywords(question) -> list[str]` |
| `retrieval/wiki_index.py` | Rewrite `WikiPageRetrieval` pipeline |
| `infra/bootstrap.py` | `WikiPageRetrieval(llm_client=llm_client)` |
| `pyproject.toml` | Add `jieba` dependency |
| `tests/test_wiki_keywords.py` | Keyword extraction tests |
| `tests/test_wiki_retrieval.py` | Replace old hash-index tests with routing fixtures |

---

### Task 1: `extract_keywords` + jieba dependency

**Files:**
- Create: `retrieval/wiki_keywords.py`
- Create: `tests/test_wiki_keywords.py`
- Modify: `pyproject.toml` (add `"jieba>=0.42.1"` to `[project].dependencies`)

**Interfaces:**
- Produces: `extract_keywords(text: str) -> list[str]` — deduped, stopwords removed, order ≈ first appearance

- [ ] **Step 1: Write failing tests**

```python
# tests/test_wiki_keywords.py
from retrieval.wiki_keywords import extract_keywords


def test_extract_keywords_keeps_domain_terms():
    kws = extract_keywords("电子普通发票怎么开？")
    assert "发票" in kws or "电子普通发票" in kws
    assert "怎么" not in kws


def test_extract_keywords_empty_and_stopwords_only():
    assert extract_keywords("") == []
    assert extract_keywords("的了吗呢") == []
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `pytest tests/test_wiki_keywords.py -v`  
Expected: FAIL (`ModuleNotFoundError` or import error)

- [ ] **Step 3: Add jieba to pyproject and implement module**

```toml
# pyproject.toml — inside dependencies list, add:
  "jieba>=0.42.1",
```

```python
# retrieval/wiki_keywords.py
from __future__ import annotations

import re

_STOPWORDS = frozenset(
    {
        "的", "了", "吗", "呢", "啊", "吧", "么", "呀", "哦", "嗯",
        "是", "在", "有", "和", "与", "及", "或", "被", "把", "让",
        "就", "都", "也", "还", "很", "太", "更", "最", "会", "能",
        "可以", "怎么", "什么", "哪个", "哪些", "如何", "请问", "一下",
        "这个", "那个", "一个", "我们", "你们", "他们", "自己",
        "a", "an", "the", "is", "are", "to", "of", "for", "in", "on",
    }
)
_TOKEN_RE = re.compile(r"[\w\u4e00-\u9fff]+", re.UNICODE)


def extract_keywords(text: str) -> list[str]:
    raw = (text or "").strip()
    if not raw:
        return []
    tokens: list[str] = []
    try:
        import jieba

        tokens = [t.strip() for t in jieba.lcut(raw) if t and t.strip()]
    except Exception:
        tokens = _TOKEN_RE.findall(raw)
    seen: set[str] = set()
    out: list[str] = []
    for token in tokens:
        if len(token) == 1 and not ("\u4e00" <= token <= "\u9fff"):
            continue
        if token.lower() in _STOPWORDS or token in _STOPWORDS:
            continue
        if token in seen:
            continue
        seen.add(token)
        out.append(token)
    return out
```

Install: `pip install -e ".[dev]"` (or `pip install jieba`) so tests can import jieba.

- [ ] **Step 4: Run tests — expect PASS**

Run: `pytest tests/test_wiki_keywords.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml retrieval/wiki_keywords.py tests/test_wiki_keywords.py
git commit -m "feat: add wiki keyword extraction with jieba"
```

---

### Task 2: Skip gates + rewrite `WikiPageRetrieval` shell

**Files:**
- Modify: `retrieval/wiki_index.py` (replace class body; delete hash helpers)
- Modify: `tests/test_wiki_retrieval.py` (replace obsolete meta/hash tests with skip + fixture helpers)

**Interfaces:**
- Consumes: `extract_keywords`
- Produces:
  - `WikiPageRetrieval(llm_client=None)`
  - `index_wiki_root(root) -> None` stores `Path` only
  - `search(query, top_k=5) -> list[Hit]`
  - helpers used later: `_list_leaf_pages`, `_read_index_text`, `_WIKI_TOP_K_CAP = 5`

- [ ] **Step 1: Replace tests with skip cases + shared fixture helpers**

Delete/replace contents of `tests/test_wiki_retrieval.py` with:

```python
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from wiki.paths import compile_wiki_root


def _write_page(wiki_root: Path, rel: str, title: str, body: str, related: list[str] | None = None) -> None:
    path = wiki_root / f"{rel}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "---",
        "type: source_page",
        "---",
        "",
        f"# {title}",
        "",
        "## 摘要",
        body,
        "",
    ]
    if related:
        lines.append("## 相关主题")
        for item in related:
            lines.append(f"- [[{item}|{item.split('/')[-1]}]]")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_index(wiki_root: Path, entries: list[tuple[str, str, str]]) -> None:
    # entries: (path_no_md, title, blurb)
    lines = ["---", "type: index", "---", "", "# Wiki Index", "", "## 主题", ""]
    for path, title, blurb in entries:
        lines.append(f"- [[{path}|{title}]] — {blurb}")
    (wiki_root / "index.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_search_skips_without_index(tmp_path: Path):
    from retrieval.wiki_index import WikiPageRetrieval

    wiki_root = compile_wiki_root(tmp_path, "kb-wiki")
    wiki_root.mkdir(parents=True)
    _write_page(wiki_root, "政策/发票政策", "发票政策", "电子发票说明")
    llm = MagicMock()
    llm.is_configured = True
    retrieval = WikiPageRetrieval(llm_client=llm)
    retrieval.index_wiki_root(wiki_root)
    assert retrieval.search("发票") == []
    llm.chat_completions.assert_not_called()


def test_search_skips_without_leaf_pages(tmp_path: Path):
    from retrieval.wiki_index import WikiPageRetrieval

    wiki_root = compile_wiki_root(tmp_path, "kb-wiki")
    wiki_root.mkdir(parents=True)
    (wiki_root / "index.md").write_text("# empty\n", encoding="utf-8")
    retrieval = WikiPageRetrieval()
    retrieval.index_wiki_root(wiki_root)
    assert retrieval.search("发票") == []


def test_search_skips_without_wiki_root():
    from retrieval.wiki_index import WikiPageRetrieval

    retrieval = WikiPageRetrieval()
    assert retrieval.search("发票") == []
```

- [ ] **Step 2: Run skip tests — expect FAIL**

Run: `pytest tests/test_wiki_retrieval.py::test_search_skips_without_index tests/test_wiki_retrieval.py::test_search_skips_without_leaf_pages tests/test_wiki_retrieval.py::test_search_skips_without_wiki_root -v`  
Expected: FAIL or wrong behavior (old search may still return hits without index)

- [ ] **Step 3: Rewrite `WikiPageRetrieval` with skip + stub search**

Replace `retrieval/wiki_index.py` with:

```python
from __future__ import annotations

import json
import re
from pathlib import Path

from retrieval.ports import Hit
from retrieval.wiki_keywords import extract_keywords

_WIKI_TOP_K_CAP = 5
_INDEX_ENTRY_RE = re.compile(
    r"- \[\[([^\]|#]+)(?:\|([^\]]+))?\]\]\s*(?:—|-)?\s*(.*)$"
)
_WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:\|[^\]]+)?\]\]")


def _excerpt(text: str, limit: int = 160) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1] + "…"


def _title_from_markdown(text: str) -> str | None:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip() or None
    return None


def _keyword_count(keywords: list[str], haystack: str) -> int:
    if not keywords or not haystack:
        return 0
    return sum(1 for kw in keywords if kw and kw in haystack)


class WikiPageRetrieval:
    """Index-routed wiki retrieval (on-disk reads; no body cache)."""

    def __init__(self, llm_client=None) -> None:
        self._wiki_root: Path | None = None
        self._llm_client = llm_client

    def index_wiki_root(self, root: str | Path) -> None:
        self._wiki_root = Path(root)

    def _leaf_pages(self) -> list[Path]:
        root = self._wiki_root
        if root is None or not root.is_dir():
            return []
        pages: list[Path] = []
        for path in root.rglob("*.md"):
            if ".meta" in path.parts:
                continue
            if path.name in {"index.md", "log.md"}:
                continue
            pages.append(path)
        return pages

    def _read_text(self, path: Path) -> str | None:
        try:
            return path.read_text(encoding="utf-8")
        except OSError:
            return None

    def search(self, query: str, top_k: int = 5) -> list[Hit]:
        limit = min(max(top_k, 0), _WIKI_TOP_K_CAP)
        if limit <= 0:
            return []
        root = self._wiki_root
        if root is None or not root.is_dir():
            return []
        leaves = self._leaf_pages()
        if not leaves:
            return []
        index_path = root / "index.md"
        index_text = self._read_text(index_path)
        if not index_text:
            return []
        # Task 3+ fills pipeline; for now return [] after gates so skip tests pass
        del query, index_text
        return []
```

Keep unused imports minimal for now; Task 3 will use regex helpers — include them in this rewrite to avoid churn, or add in Task 3. Prefer including helpers now even if unused (or prefix with use in Task 3 only). **If linters complain about unused imports, add a minimal `_parse_index_entries` stub that returns `[]` and call it from `search` before `return []`.**

```python
        entries = _parse_index_entries(index_text)
        del query, entries
        return []


def _parse_index_entries(index_text: str) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    for line in index_text.splitlines():
        match = _INDEX_ENTRY_RE.match(line.strip())
        if not match:
            continue
        path = match.group(1).strip().replace("\\", "/")
        title = (match.group(2) or path.split("/")[-1]).strip()
        blurb = (match.group(3) or "").strip()
        entries.append({"path": path, "title": title, "blurb": blurb})
    return entries
```

- [ ] **Step 4: Run skip tests — expect PASS**

Run: `pytest tests/test_wiki_retrieval.py::test_search_skips_without_index tests/test_wiki_retrieval.py::test_search_skips_without_leaf_pages tests/test_wiki_retrieval.py::test_search_skips_without_wiki_root -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add retrieval/wiki_index.py tests/test_wiki_retrieval.py
git commit -m "refactor: wiki retrieval skip when missing index or pages"
```

---

### Task 3: Index seeds + weighted scoring (no hop yet)

**Files:**
- Modify: `retrieval/wiki_index.py` (`search` pipeline through score/top_k)
- Modify: `tests/test_wiki_retrieval.py` (add hit + ranking tests)

**Interfaces:**
- Consumes: `_parse_index_entries`, `extract_keywords`, `_keyword_count`
- Produces: hits from seeds only when keywords match index; `path` like `政策/发票政策.md`, `ref_id` like `政策/发票政策`

- [ ] **Step 1: Write failing tests**

```python
def test_search_index_seed_hit(tmp_path: Path):
    from retrieval.wiki_index import WikiPageRetrieval

    wiki_root = compile_wiki_root(tmp_path, "kb-wiki")
    wiki_root.mkdir(parents=True)
    _write_page(wiki_root, "政策/发票政策", "发票政策", "默认开具电子普通发票")
    _write_page(wiki_root, "物流/发货时效说明", "发货时效说明", "付款后48小时内发货")
    _write_index(
        wiki_root,
        [
            ("政策/发票政策", "发票政策", "电子普通发票与增值税专用发票说明"),
            ("物流/发货时效说明", "发货时效说明", "现货发货时效"),
        ],
    )
    retrieval = WikiPageRetrieval()
    retrieval.index_wiki_root(wiki_root)
    hits = retrieval.search("电子发票怎么开", top_k=5)
    assert hits
    assert hits[0].hit_type == "wiki"
    assert hits[0].ref_id == "政策/发票政策"
    assert hits[0].path == "政策/发票政策.md"
    assert hits[0].title == "发票政策"
    assert all(h.path != "index.md" for h in hits)


def test_search_title_outweighs_body_only(tmp_path: Path):
    from retrieval.wiki_index import WikiPageRetrieval

    wiki_root = compile_wiki_root(tmp_path, "kb-wiki")
    wiki_root.mkdir(parents=True)
    # Index blurbs avoid the rare keyword so seeds empty → full scan (Task 5).
    # For Task 3 only: put keyword in both index entries so both are seeds,
    # title page should rank higher via path+title weight.
    _write_page(wiki_root, "政策/运费政策", "运费政策", "普通说明不含特殊词")
    _write_page(wiki_root, "规则/其它", "其它", "正文多次提到包邮包邮包邮")
    _write_index(
        wiki_root,
        [
            ("政策/运费政策", "运费政策", "包邮规则"),
            ("规则/其它", "其它", "包邮相关"),
        ],
    )
    retrieval = WikiPageRetrieval()
    retrieval.index_wiki_root(wiki_root)
    hits = retrieval.search("包邮", top_k=5)
    assert hits
    assert hits[0].ref_id == "政策/运费政策"
```

- [ ] **Step 2: Run — expect FAIL**

Run: `pytest tests/test_wiki_retrieval.py::test_search_index_seed_hit tests/test_wiki_retrieval.py::test_search_title_outweighs_body_only -v`  
Expected: FAIL (empty hits)

- [ ] **Step 3: Implement seed selection + scoring in `search`**

Add helpers and replace the end of `search`:

```python
def _page_rel_id(root: Path, file_path: Path) -> str:
    return file_path.relative_to(root).as_posix().removesuffix(".md")


def _score_candidates(
    root: Path,
    keywords: list[str],
    candidate_rels: list[str],
) -> list[Hit]:
    scored: list[tuple[float, Hit]] = []
    for rel in candidate_rels:
        file_path = root / f"{rel}.md"
        text = file_path.read_text(encoding="utf-8") if file_path.is_file() else None
        if text is None:
            continue
        title = _title_from_markdown(text) or rel.split("/")[-1]
        path = f"{rel}.md"
        title_hits = _keyword_count(keywords, f"{rel} {title}")
        body_hits = _keyword_count(keywords, text)
        raw = 2 * title_hits + body_hits
        if raw <= 0:
            continue
        hit = Hit(
            score=float(raw),
            snippet=_excerpt(text),
            hit_type="wiki",
            ref_id=rel,
            title=title,
            path=path,
        )
        scored.append((float(raw), hit))
    if not scored:
        return []
    max_raw = max(raw for raw, _ in scored)
    hits = []
    for raw, hit in scored:
        hit.score = raw / max_raw if max_raw else 0.0
        hits.append(hit)
    hits.sort(key=lambda item: item.score, reverse=True)
    return hits


# inside search, after reading index_text:
        keywords = extract_keywords(query)
        entries = _parse_index_entries(index_text)
        seeds: list[str] = []
        for entry in entries:
            hay = f"{entry['path']} {entry['title']} {entry['blurb']}"
            if _keyword_count(keywords, hay) > 0:
                seeds.append(entry["path"])
        # Task 4 adds hop; Task 5 adds full scan
        if seeds:
            candidates = list(dict.fromkeys(seeds))
        else:
            candidates = []  # Task 5 fills full-scan
        hits = _score_candidates(root, keywords, candidates)
        return hits[:limit]
```

Wrap single-file read in try/except OSError → skip (match `_read_text`).

- [ ] **Step 4: Run — expect PASS**

Run: `pytest tests/test_wiki_retrieval.py::test_search_index_seed_hit tests/test_wiki_retrieval.py::test_search_title_outweighs_body_only -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add retrieval/wiki_index.py tests/test_wiki_retrieval.py
git commit -m "feat: score wiki pages from index keyword seeds"
```

---

### Task 4: Existence-filtered 1-hop

**Files:**
- Modify: `retrieval/wiki_index.py`
- Modify: `tests/test_wiki_retrieval.py`

**Interfaces:**
- Produces: `_expand_one_hop(root, seed_rel, text) -> list[str]`

- [ ] **Step 1: Write failing test**

```python
def test_one_hop_keeps_real_pages_drops_entities(tmp_path: Path):
    from retrieval.wiki_index import WikiPageRetrieval

    wiki_root = compile_wiki_root(tmp_path, "kb-wiki")
    wiki_root.mkdir(parents=True)
    _write_page(
        wiki_root,
        "政策/发票政策",
        "发票政策",
        "发票说明\n\n## 相关实体\n- [[电子普通发票|电子普通发票]]\n",
        related=["政策/运费政策", "source-政策__发票"],
    )
    _write_page(wiki_root, "政策/运费政策", "运费政策", "运费与发票无关的邻居页")
    _write_index(
        wiki_root,
        [("政策/发票政策", "发票政策", "电子普通发票开具说明")],
    )
    retrieval = WikiPageRetrieval()
    retrieval.index_wiki_root(wiki_root)
    hits = retrieval.search("电子普通发票", top_k=5)
    ref_ids = {h.ref_id for h in hits}
    assert "政策/发票政策" in ref_ids
    assert "政策/运费政策" in ref_ids
    assert all(not (rid or "").startswith("source-") for rid in ref_ids)
    assert "电子普通发票" not in ref_ids
```

- [ ] **Step 2: Run — expect FAIL** (neighbor missing)

Run: `pytest tests/test_wiki_retrieval.py::test_one_hop_keeps_real_pages_drops_entities -v`

- [ ] **Step 3: Implement hop expansion**

```python
def _expand_one_hop(root: Path, text: str) -> list[str]:
    neighbors: list[str] = []
    for match in _WIKILINK_RE.finditer(text):
        target = match.group(1).strip().replace("\\", "/")
        if target.startswith(("source-", "chunk-")):
            continue
        if (root / f"{target}.md").is_file():
            neighbors.append(target)
    return neighbors


# when building candidates from seeds:
        if seeds:
            candidates: list[str] = []
            for seed in seeds:
                if seed not in candidates:
                    candidates.append(seed)
                seed_file = root / f"{seed}.md"
                seed_text = self._read_text(seed_file)
                if not seed_text:
                    continue
                for neighbor in _expand_one_hop(root, seed_text):
                    if neighbor not in candidates:
                        candidates.append(neighbor)
        else:
            candidates = []
```

- [ ] **Step 4: Run — expect PASS**

Run: `pytest tests/test_wiki_retrieval.py::test_one_hop_keeps_real_pages_drops_entities -v`

- [ ] **Step 5: Commit**

```bash
git add retrieval/wiki_index.py tests/test_wiki_retrieval.py
git commit -m "feat: expand wiki seeds one hop with real page filter"
```

---

### Task 5: Full scan when index exists but seeds empty

**Files:**
- Modify: `retrieval/wiki_index.py`
- Modify: `tests/test_wiki_retrieval.py`

**Interfaces:**
- Produces: full-scan candidate list from `_leaf_pages` when `seeds` empty (still no hop)

- [ ] **Step 1: Write failing test**

```python
def test_full_scan_when_index_misses_keywords(tmp_path: Path):
    from retrieval.wiki_index import WikiPageRetrieval

    wiki_root = compile_wiki_root(tmp_path, "kb-wiki")
    wiki_root.mkdir(parents=True)
    _write_page(wiki_root, "政策/发票政策", "发票政策", "正文含有稀有词夸克发票")
    _write_page(
        wiki_root,
        "物流/发货时效说明",
        "发货时效说明",
        "无关内容",
        related=["政策/发票政策"],
    )
    _write_index(
        wiki_root,
        [
            ("政策/发票政策", "发票政策", "电子普通发票"),
            ("物流/发货时效说明", "发货时效说明", "发货时效"),
        ],
    )
    retrieval = WikiPageRetrieval()
    retrieval.index_wiki_root(wiki_root)
    hits = retrieval.search("夸克发票", top_k=5)
    assert hits
    assert hits[0].ref_id == "政策/发票政策"
    # full scan must NOT pull related hop from 发货页
    assert len(hits) == 1 or all(h.ref_id != "物流/发货时效说明" or "夸克" not in (h.snippet or "") for h in hits)
```

Stronger assertion: only pages with keyword score > 0; 发货 page body has no 夸克 → not in hits.

```python
    assert {h.ref_id for h in hits} == {"政策/发票政策"}
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement else branch**

```python
        if seeds:
            ...  # existing hop logic
        else:
            candidates = [_page_rel_id(root, path) for path in leaves]
        hits = _score_candidates(root, keywords, candidates)
        if hits:
            return hits[:limit]
        # Task 6: LLM fallback
        return []
```

- [ ] **Step 4: Run — expect PASS**

Run: `pytest tests/test_wiki_retrieval.py::test_full_scan_when_index_misses_keywords -v`

- [ ] **Step 5: Commit**

```bash
git add retrieval/wiki_index.py tests/test_wiki_retrieval.py
git commit -m "feat: full-scan wiki leaves when index keywords miss"
```

---

### Task 6: LLM fallback + bootstrap injection

**Files:**
- Modify: `retrieval/wiki_index.py`
- Modify: `infra/bootstrap.py` (`WikiPageRetrieval(llm_client=llm_client)` — construct **after** `llm_client = OpenAiCompatibleClient(...)` or reorder)
- Modify: `tests/test_wiki_retrieval.py`

**Interfaces:**
- Consumes: `llm_client.is_configured`, `llm_client.chat_completions(messages) -> str`
- Produces: `_llm_select_paths(question, index_text, limit) -> list[str]`

**Bootstrap note:** Today `wiki_retrieval` is built before `llm_client`. Reorder:

```python
    llm_client = OpenAiCompatibleClient(settings)
    wiki_retrieval: WikiPageRetrieval | None = None
    if settings.wiki_compile:
        wiki_retrieval = WikiPageRetrieval(llm_client=llm_client)
        wiki_root = compile_wiki_root(settings.data_root, knowledge_base_id)
        if wiki_root.is_dir():
            wiki_retrieval.index_wiki_root(wiki_root)
```

Move the earlier wiki block down next to this (remove duplicate).

- [ ] **Step 1: Write failing tests**

```python
def test_llm_fallback_selects_paths(tmp_path: Path):
    from retrieval.wiki_index import WikiPageRetrieval

    wiki_root = compile_wiki_root(tmp_path, "kb-wiki")
    wiki_root.mkdir(parents=True)
    _write_page(wiki_root, "政策/发票政策", "发票政策", "无匹配关键词正文xyz")
    _write_index(wiki_root, [("政策/发票政策", "发票政策", "完全不相关摘要")])

    llm = MagicMock()
    llm.is_configured = True
    llm.chat_completions.return_value = '{"paths": ["政策/发票政策", "不存在/页"]}'

    retrieval = WikiPageRetrieval(llm_client=llm)
    retrieval.index_wiki_root(wiki_root)
    hits = retrieval.search("完全无关的问法zzz", top_k=5)
    assert [h.ref_id for h in hits] == ["政策/发票政策"]
    llm.chat_completions.assert_called_once()


def test_llm_fallback_bad_json_returns_empty(tmp_path: Path):
    from retrieval.wiki_index import WikiPageRetrieval

    wiki_root = compile_wiki_root(tmp_path, "kb-wiki")
    wiki_root.mkdir(parents=True)
    _write_page(wiki_root, "政策/发票政策", "发票政策", "abc")
    _write_index(wiki_root, [("政策/发票政策", "发票政策", "xyz")])
    llm = MagicMock()
    llm.is_configured = True
    llm.chat_completions.return_value = "not-json"
    retrieval = WikiPageRetrieval(llm_client=llm)
    retrieval.index_wiki_root(wiki_root)
    assert retrieval.search("zzz无关词", top_k=5) == []


def test_top_k_capped_at_five(tmp_path: Path):
    from retrieval.wiki_index import WikiPageRetrieval

    wiki_root = compile_wiki_root(tmp_path, "kb-wiki")
    wiki_root.mkdir(parents=True)
    entries = []
    for i in range(6):
        rel = f"政策/页{i}"
        _write_page(wiki_root, rel, f"页{i}", f"共同关键词阿尔法 {i}")
        entries.append((rel, f"页{i}", f"阿尔法摘要{i}"))
    _write_index(wiki_root, entries)
    retrieval = WikiPageRetrieval()
    retrieval.index_wiki_root(wiki_root)
    hits = retrieval.search("阿尔法", top_k=8)
    assert len(hits) == 5
```

- [ ] **Step 2: Run — expect FAIL** on LLM tests

Run: `pytest tests/test_wiki_retrieval.py::test_llm_fallback_selects_paths tests/test_wiki_retrieval.py::test_llm_fallback_bad_json_returns_empty tests/test_wiki_retrieval.py::test_top_k_capped_at_five -v`

- [ ] **Step 3: Implement LLM fallback**

```python
def _hits_from_paths(root: Path, paths: list[str], limit: int) -> list[Hit]:
    hits: list[Hit] = []
    for index, rel in enumerate(paths[:limit]):
        rel = rel.strip().replace("\\", "/").removesuffix(".md")
        if not rel or ".." in rel.split("/"):
            continue
        file_path = root / f"{rel}.md"
        text = file_path.read_text(encoding="utf-8") if file_path.is_file() else None
        if text is None:
            continue
        title = _title_from_markdown(text) or rel.split("/")[-1]
        score = 1.0 - index * 0.01
        hits.append(
            Hit(
                score=score,
                snippet=_excerpt(text),
                hit_type="wiki",
                ref_id=rel,
                title=title,
                path=f"{rel}.md",
            )
        )
    return hits


def _llm_select_paths(llm_client, question: str, index_text: str, limit: int) -> list[str]:
    if llm_client is None or not getattr(llm_client, "is_configured", False):
        return []
    prompt = (
        "你是 Wiki 路由助手。根据用户问题，从 index.md 中选择最相关的页面路径。"
        f"最多返回 {limit} 条。只输出 JSON：{{\"paths\": [\"hub/leaf\", ...]}}。\n\n"
        f"## 用户问题\n{question}\n\n## index.md\n{index_text}\n"
    )
    try:
        raw = llm_client.chat_completions(
            [{"role": "user", "content": prompt}],
            temperature=0.0,
            timeout=60.0,
        )
    except Exception:
        return []
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return []
    paths = payload.get("paths") if isinstance(payload, dict) else None
    if not isinstance(paths, list):
        return []
    out: list[str] = []
    for item in paths:
        if isinstance(item, str) and item.strip():
            out.append(item.strip())
        if len(out) >= limit:
            break
    return out


# end of search after scoring:
        if hits:
            return hits[:limit]
        paths = _llm_select_paths(self._llm_client, query, index_text, limit)
        return _hits_from_paths(root, paths, limit)
```

Use try/except OSError in `_hits_from_paths` instead of bare `read_text` if preferred.

- [ ] **Step 4: Wire bootstrap**

Reorder so `llm_client` exists before `WikiPageRetrieval(llm_client=llm_client)`.

- [ ] **Step 5: Run all wiki retrieval tests**

Run: `pytest tests/test_wiki_retrieval.py tests/test_wiki_keywords.py -v`  
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add retrieval/wiki_index.py infra/bootstrap.py tests/test_wiki_retrieval.py
git commit -m "feat: LLM wiki path fallback and inject llm_client"
```

---

### Task 7: Regression sweep

**Files:**
- Verify only (fix if broken): any test importing old wiki hash behavior

- [ ] **Step 1: Run related suites**

Run: `pytest tests/test_wiki_retrieval.py tests/test_wiki_keywords.py tests/test_retrieval.py tests/test_chunk_retrieval.py -v`  
Expected: PASS (or only unrelated failures — fix wiki-related breaks only)

- [ ] **Step 2: Grep for stale assumptions**

Run: `rg "char.hash|bm25_score|_IndexedPage|topic-refund" retrieval tests -g "*.py"`  
Expected: no matches in `retrieval/wiki_index.py`; update any leftover test refs.

- [ ] **Step 3: Commit only if fixes were needed**

```bash
git add -u retrieval tests
git commit -m "test: align suites with wiki index routing"
```

(Skip commit if nothing changed.)

---

## Spec coverage checklist

| Spec item | Task |
|-----------|------|
| D1 keywords / jieba | Task 1 |
| D9 skip no data / no index | Task 2 |
| D2 seeds only when hit | Task 3 |
| D5 weighted score + top 5 | Task 3, 6 |
| D4 1-hop existence filter | Task 4 |
| D3 full scan on keyword miss | Task 5 |
| D6 LLM JSON paths | Task 6 |
| D7 bootstrap llm | Task 6 |
| D8 no body cache | Task 2+ |
| Tests §6 | Tasks 2–6 |

## Placeholder / consistency review

- Count mode fixed: substring per keyword  
- `path` always `rel.md`; `ref_id` always `rel` without `.md`  
- `_WIKI_TOP_K_CAP = 5` shared  
- No TBD left in tasks
