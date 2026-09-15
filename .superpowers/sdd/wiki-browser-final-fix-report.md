# Wiki Browser Final Fix Report

**Date**: 2026-09-15  
**Branch**: `feature/wiki-browser`  
**Commit message**: `fix: wiki browser tree index reachability and hub grouping`

## Summary

One-pass fix for all Important findings from the Wiki Browser final whole-branch review, plus two cheap Minor items.

## Fixes

### 1. Hub expression precedence (`wiki/browser.py`)

Replaced ambiguous:
`meta.hub or page_id.split("/", 1)[0] if "/" in page_id else "其他"`

with explicit if/elif/else so `meta.hub` wins for flat `page_id` values (no `/`).

**Test**: `test_build_tree_uses_meta_hub_for_flat_page_id` — flat `flat` with `hub="售后"` groups under 售后.

### 2. `index.md` reachable in tree

When `{wiki_root}/index.md` exists, `build_wiki_tree` prepends hub **总览** with page `page_id="index"` (title from first `# ` H1, else `"总览"`). Response schema unchanged (`hubs` only).

`read_wiki_page`: when meta is missing, prefer first H1 title over `path.stem`.

Frontend already prefers `index` via `pickDefaultPageId` / `collectPageIds` once it appears in the tree.

**Tests**:
- `test_build_tree_includes_index_when_present`
- `test_read_wiki_page_prefers_h1_when_meta_missing`
- API: `test_wiki_tree_and_page_and_search` asserts tree contains `index` and `GET .../pages/index` works

### 3. Skip `{hub}/_index.md`

`build_wiki_tree` and `search_wiki_pages` skip entries whose `meta.path` ends with `_index.md` (same rule as related/source_plan).

**Test**: `test_build_tree_and_search_skip_hub_index`

### 4. Minor — CSS mark highlight

`.wiki-article mark` → also `.wiki-page mark` so sidebar search snippets get the same highlight styles.

### 5. Minor — dual loading indicator

Removed `isSearching` from page-level `isLoading` so search-only loads do not show a second global “正在加载 Wiki…”. Sidebar still shows its own searching state.

## Files changed

- `wiki/browser.py`
- `tests/test_wiki_browser.py`
- `tests/test_admin_wiki_browser_api.py`
- `web/src/pages/WikiPage.tsx`
- `web/src/styles/global.css`

## Test evidence

```text
$ pytest tests/test_wiki_browser.py tests/test_admin_wiki_browser_api.py -q
............                                                             [100%]
12 passed, 1 warning in 2.90s

$ cd web && npx vitest run src/pages/WikiPage.test.tsx src/components/WikiMarkdown.test.tsx
 ✓ src/components/WikiMarkdown.test.tsx (2 tests) 292ms
 ✓ src/pages/WikiPage.test.tsx (9 tests) 994ms
 Test Files  2 passed (2)
      Tests  11 passed (11)
```

## Remaining concerns

- Hub **总览** is synthetic and always prepended when `index.md` exists; if `pages.json` ever also listed a real hub named `总览`, those pages are currently skipped to avoid duplication with the synthetic hub (unlikely in current compile output).
- Search still does not index root `index.md` itself (only meta-backed leaf pages); tree navigation + `read_wiki_page("index")` cover browsing.
