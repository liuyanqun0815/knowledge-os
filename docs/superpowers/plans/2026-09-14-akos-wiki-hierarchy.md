# Wiki Hierarchy (Hub/Leaf/Snippet) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace flat `topic-*.md` wiki pages with hub folders + leaf pages (no `topic-` prefix), merge phrase-level snippets into parent pages, and keep wiki retrieval/wikilinks working.

**Architecture:** A pure `assign_wiki_hierarchy(clusters|raw_names) -> HierarchyPlan` maps each topic to hub/leaf/snippet using domain seed maps + heuristics. `wiki/links.py` emits path-based names (`客服话术/沟通规范`). `compile.py` writes `{hub}/_index.md` and `{hub}/{leaf}.md`, folds snippets into target pages, limits related links to same hub, and optionally deletes legacy flat `topic-*.md`. `WikiPageRetrieval` recursively indexes markdown under the wiki root.

**Tech Stack:** Python 3, existing `wiki/compile.py` / `wiki/links.py` / `retrieval/wiki_index.py`, pytest, Settings (`AKOS_WIKI_*`).

## Global Constraints

- Spec: `docs/superpowers/specs/2026-09-14-akos-wiki-hierarchy-design.md` (confirmed)
- Default `AKOS_WIKI_HIERARCHY=true`; `false` preserves flat `topic-` behavior
- Wikilinks prefer **path form** `[[hub/leaf|label]]` to avoid collisions
- Snippets must not create standalone `.md` files
- Related topics: same hub only (cap `AKOS_WIKI_MAX_RELATED`, default 12)
- black `max_line_length=120`; no `from module import *`; TDD; commit per task
- Dirty tree: stage only task files

## File map

| File | Responsibility |
|------|----------------|
| `infra/settings.py`, `.env.example`, `README.md` | hierarchy flags |
| `wiki/hierarchy.py` | `HierarchyAssignment`, `HierarchyPlan`, `assign_wiki_hierarchy` |
| `domains/ecommerce_cs/wiki_hierarchy.py` | seed parent/snippet maps |
| `wiki/links.py` | path-based topic page names / wikilinks |
| `wiki/compile.py` | write hub dirs, fold snippets, related=same hub, migrate flat |
| `wiki/export.py` | align topic export paths when hierarchy on |
| `retrieval/wiki_index.py` | recursive `**/*.md` index |
| `wiki/meta.py` | optional `hub`/`role` fields on `WikiPageMeta` |
| `tests/test_wiki_hierarchy*.py`, compile/retrieval updates | coverage |

---

### Task 1: Settings

**Files:**
- Modify: `infra/settings.py`, `.env.example`, `README.md`
- Test: `tests/test_wiki_hierarchy_settings.py`

**Interfaces:**
- Produces: `wiki_hierarchy: bool = True`, `wiki_hierarchy_llm: bool = False`, `wiki_migrate_flat: bool = True`, `wiki_max_related: int = 12`

- [ ] **Step 1: Failing defaults test**
- [ ] **Step 2: Run FAIL**
- [ ] **Step 3: Implement settings + docs**
- [ ] **Step 4: PASS**
- [ ] **Step 5: Commit** `feat: add wiki hierarchy settings`

---

### Task 2: Hierarchy assignment (pure function + ecommerce seeds)

**Files:**
- Create: `wiki/hierarchy.py`
- Create: `domains/ecommerce_cs/wiki_hierarchy.py` (seed maps)
- Test: `tests/test_wiki_hierarchy.py`

**Interfaces:**
- Produces:

```python
@dataclass(frozen=True)
class HierarchyAssignment:
    raw_name: str
    hub: str
    leaf: str | None  # None => hub-only (_index)
    role: str  # "hub" | "leaf" | "snippet"
    target_leaf: str | None  # for snippet: which leaf (or None => hub _index)

@dataclass
class HierarchyPlan:
    assignments: dict[str, HierarchyAssignment]  # key = display/raw topic name
    hubs: dict[str, list[str]]  # hub -> leaf display names (excl snippets)
```

- `assign_wiki_hierarchy(names: list[str], *, seeds: dict | None = None) -> HierarchyPlan`
- Seeds API example: `get_ecommerce_wiki_seeds() -> dict` with keys `parents` / `snippets` mapping raw→(hub, leaf, role)

**Seed examples (ecommerce_cs):**
- snippets: 不知道/不归我管/你找别人/没办法/不可能 → hub `客服话术`, target_leaf `禁用表达`
- leaves: 客服开场/开场 → `客服话术`/`开场`; 客服沟通 → `客服话术`/`沟通规范`
- hubs: 投诉升级 related 一级/二级/三级 → hub `投诉升级`

Heuristics when unmapped: short (≤4) → snippet under most frequent hub in batch or `未分类`; else hub=self leaf=None or prefix match.

- [ ] **Step 1: Failing tests** — unknown short phrase → snippet; seeded 不知道 → 客服话术/禁用表达
- [ ] **Step 2–4: Implement + PASS**
- [ ] **Step 5: Commit** `feat: assign wiki hub/leaf/snippet hierarchy`

---

### Task 3: Path-based links (no topic- prefix)

**Files:**
- Modify: `wiki/links.py`
- Update callers/tests that assert `topic-尺码选择`
- Test: `tests/test_wiki_links.py` (new or extend)

**Interfaces:**
- Produces:
  - `topic_page_path(hub: str, leaf: str | None = None) -> str` → `客服话术/_index` or `客服话术/沟通规范`
  - `topic_wikilink(hub, leaf=None, label=None) -> str` → `[[客服话术/沟通规范|沟通规范]]`
- When `hierarchy_enabled=False` (pass flag or keep legacy helpers): keep `topic-{name}` for rollback

Recommended: keep `topic_page_name(name)` as thin wrapper only for legacy mode; new code uses path helpers.

- [ ] **Step 1–5: TDD + commit** `feat: use path-based wiki topic links without topic- prefix`

---

### Task 4: Compile writes hub folders + folds snippets

**Files:**
- Modify: `wiki/compile.py`, optionally `wiki/meta.py` (`hub`, `role`)
- Wire: load ecommerce seeds when domain is ecommerce_cs (from settings/domain_type if available on knowledge/deps; else always merge ecommerce seeds + generic heuristics)
- Test: `tests/test_wiki_compile_hierarchy.py`

**Behavior when `settings.wiki_hierarchy`:**
1. Build plan from active cluster names (+ chunk topics)
2. For each hub: write `{hub}/_index.md` (summary of hub + child links + folded hub-level snippets)
3. For each leaf: write `{hub}/{leaf}.md` with claims/chunks for that leaf **plus** snippets targeting it
4. Related topics: same hub only, ≤ `wiki_max_related`
5. `index.md`: group by hub
6. If `wiki_migrate_flat`: delete `{wiki_root}/topic-*.md`
7. Update meta with relative `path`, `hub`, `role`

When hierarchy false: existing flat `topic-` behavior unchanged.

- [ ] **Step 1: Failing test** — compile two clusters 不知道+客服沟通 → files under `客服话术/`, no `topic-不知道.md`, 禁用内容 in 禁用表达 or 沟通规范 per seeds
- [ ] **Step 2–4: Implement + PASS** (update older compile tests that expect `topic-` paths)
- [ ] **Step 5: Commit** `feat: compile hierarchical wiki pages and fold snippets`

---

### Task 5: Wiki retrieval recursive index + export align

**Files:**
- Modify: `retrieval/wiki_index.py` — `rglob("*.md")`, skip `.meta`, skip none or skip only frontmatter-less if needed; `path` relative with `/`
- Modify: `wiki/export.py` — when hierarchy settings on, write topic pages to hub paths (or call shared path helper); avoid regenerating flat topic- only
- Test: `tests/test_wiki_retrieval.py` updates; export test if needed

- [ ] **Step 1: Failing test** — nested `客服话术/沟通规范.md` is searchable
- [ ] **Step 2–4: Implement + PASS**
- [ ] **Step 5: Commit** `feat: index nested wiki pages and align export paths`

---

### Task 6: Regression + docs note

- [ ] **Step 1: Run**

```bash
pytest tests/test_wiki_hierarchy_settings.py tests/test_wiki_hierarchy.py tests/test_wiki_links.py tests/test_wiki_compile.py tests/test_wiki_compile_llm.py tests/test_wiki_compile_hierarchy.py tests/test_wiki_retrieval.py tests/test_wiki_export.py tests/test_admin_wiki_compile_api.py -q
```

- [ ] **Step 2: Fix hierarchy-related failures**
- [ ] **Step 3: Commit only if fixes** `test: wiki hierarchy regression`
- [ ] **Step 4: README** one paragraph on `wiki/{hub}/_index.md` layout (if not done in Task 1)

---

## Spec coverage

| Spec item | Task |
|-----------|------|
| Settings / migrate / max related | 1 |
| Hub/leaf/snippet assignment + seeds | 2 |
| No topic- prefix, path wikilinks | 3 |
| Directory compile + fold + related | 4 |
| Retrieval recursive + export | 5 |
| Acceptance / regression | 6 |

## Out of scope

- Full concepts/sources/entities multi-tree (方案 C)
- Hierarchy LLM (`wiki_hierarchy_llm` setting stub only until optional follow-up)
- Frontend wiki browser
