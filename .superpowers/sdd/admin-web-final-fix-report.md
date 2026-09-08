# Admin Web Final Fix Report

## 2026-09-08

### Changes

- Every orchestrator lookup checks that a persisted knowledge base is active; archived entries are evicted from the cache and return HTTP 400.
- Archiving immediately evicts the matching orchestrator cache entry.
- `SourcesPage` ignores stale list responses after a knowledge-base switch.
- `AskPage` no longer exposes or sends unsupported `as_of` data and shows the Phase 2.2 helper text.
- `KbSwitcher` reloads after create/archive events and on window focus.
- Added the Admin Web design/plan and referenced Phase 2 design documents.

### Verification

- `cd web && npm test`: 9 files passed, 30 tests passed.
- `cd web && npm run build`: TypeScript and Vite build passed.
- `python -m pytest tests/test_api.py::test_ask_rejects_archived_kb_even_when_orchestrator_is_cached -q`:
  1 passed, 1 dependency deprecation warning.
- `python -m black --line-length 120 app/deps.py admin_api/routes_knowledge_bases.py tests/test_api.py`:
  3 files unchanged.

### Commits

- `342a2d1` — docs: add admin web design and plans
- `99e48a8` — fix: address admin web review findings
