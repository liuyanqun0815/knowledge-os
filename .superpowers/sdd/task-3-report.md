# Task 3 Report: Index seeds + weighted scoring (no hop)

**Status:** DONE  
**Date:** 2026-09-15  
**Branch:** feat/wiki-index-routing  
**Commit:** 8ff96df — `feat: score wiki pages from index keyword seeds`

## TDD Execution

| Step | Action | Result |
|------|--------|--------|
| 1 | Append `test_search_index_seed_hit`, `test_search_title_outweighs_body_only` | Created |
| 2 | Run new tests (expect FAIL) | **RED** — `assert hits` failed (empty) |
| 3 | Implement `_page_rel_id`, `_score_candidates`, seed selection in `search` | Implemented |
| 4 | Run all wiki retrieval tests (expect PASS) | **GREEN** — 5 passed in 1.38s |
| 5 | Commit staged task files | Done |

### RED Evidence (Step 2)

```text
pytest tests/test_wiki_retrieval.py::test_search_index_seed_hit \
  tests/test_wiki_retrieval.py::test_search_title_outweighs_body_only -v -p no:opik
FAILED test_search_index_seed_hit - assert []
FAILED test_search_title_outweighs_body_only - assert []
```

### GREEN Evidence (Step 4)

```text
pytest tests/test_wiki_retrieval.py -v -p no:opik
5 passed in 1.38s
```

## Files Changed

| File | Change |
|------|--------|
| `retrieval/wiki_index.py` | Added `_page_rel_id`, `_score_candidates`; wired `extract_keywords` → index seed match → weighted score → top_k |
| `tests/test_wiki_retrieval.py` | Appended seed hit + title-vs-body ranking tests; kept skip gates + helpers |

## Self-Review

**Matches brief:**
- Skip gates unchanged; empty seeds → `candidates=[]` (Task 5 full scan)
- Seeds from index `path+title+blurb` keyword match
- `_score_candidates`: 2× title zone + 1× body, normalize, sort desc, OSError-safe read
- Hit fields: `hit_type=wiki`, `ref_id` without `.md`, `path` with `.md`
- No 1-hop

**Deviation (required for ranking test):**
- `_score_candidates` accepts optional `index_by_path`; title zone includes index `title+blurb`
- Body hits exclude keywords already in title zone (prevents index-blurb seed + body-only page from outranking title-route page on tie)

## Concerns

1. **Brief `_score_candidates` alone cannot pass `test_search_title_outweighs_body_only`** — page with keyword only in index blurb scores 0 on file-only title_hits; index metadata + body dedup needed.
2. **`_page_rel_id` unused until Task 4** — added per brief.
3. **Empty seeds still return `[]`** until Task 5 full scan.

## Next Task

Task 4: 1-hop neighbor expansion from seed pages.

## Review Fix (2026-09-15)

**Issue:** `_score_candidates` deviated from SPEC — used index blurb in title zone and deduped body hits.

**Fix:**
- Restored `title_hits = _keyword_count(keywords, f"{rel} {title}")`, `body_hits = _keyword_count(keywords, text)`, `raw = 2 * title_hits + body_hits`
- Removed `index_by_path` parameter
- Updated `test_search_title_outweighs_body_only`: page A title `# 包邮政策` (body无包邮), page B body-only 包邮; both seeded via index blurb

### GREEN Evidence (review fix)

```text
pytest tests/test_wiki_retrieval.py -v -p no:opik
5 passed in 1.29s
```

**Commit:** 0fd493f — `fix: restore wiki page scoring to path-title body formula`
