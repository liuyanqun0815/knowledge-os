# Task 6 Report: Regression sweep

## Status
DONE

## Changes
None — suite already aligned with async `202` accept; no test/code fixes required.

## Tests
```bash
# Prerequisite: temporary stash of WIP admin_api/routes_wiki.py
# (imports missing build_wiki_compile_deps from infra.bootstrap)
git stash push -m "temp-task6-routes-wiki" -- admin_api/routes_wiki.py

pytest tests/test_source_upload_zip.py tests/test_source_tree_ops.py tests/test_upload_jobs.py tests/test_upload_resume.py tests/test_hybrid_extraction_api.py tests/test_evolution_api.py tests/test_admin_kb_api.py tests/test_doc_extract.py -q --tb=line
```

### Full output summary
```
..............................ss.......                                  [100%]
============================== warnings summary ===============================
C:\Users\EDY\miniconda3\Lib\site-packages\starlette\testclient.py:53
  C:\Users\EDY\miniconda3\Lib\site-packages\starlette\testclient.py:53: DeprecationWarning: The anyio.abc.BlockingPortal alias is deprecated, use anyio.from_thread.BlockingPortal instead.
    _PortalFactoryType = Callable[[], AbstractContextManager[anyio.abc.BlockingPortal]]

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
37 passed, 2 skipped, 1 warning in 5.62s
```

PASS — **37 passed, 2 skipped**, exit 0.

```bash
git stash pop  # restored WIP routes_wiki.py
```

### Remaining `status_code == 200` in suite
Non-upload paths only (GET sources poll, list/detail/patch KB, evolution/compile history). No upload accept still expecting `200`.

## Commit
none (no fixes)

## Notes / Concerns
- Local WIP `admin_api/routes_wiki.py` still imports missing `build_wiki_compile_deps`; collection/import fails unless that file is at HEAD for the run (stashed for pytest only; not committed).
- Starlette `BlockingPortal` DeprecationWarning from testclient (environment noise).

---

# Final whole-branch review fixes

## Status
DONE

## Changes
1. **upload-tree**: Restored two-phase flow — validate all paths/suffixes first; only then `write_bytes` + schedule (no orphan files on mid-batch 400).
2. **process_uploaded_source**: `enrich_chunks` wrapped in its own try/except; logs failure and does **not** mark source `failed` after successful ingest + `enrich_source`.
3. **SourcesPage polling**: `pollGenerationRef` cancels prior polls on unmount / `kbId` change / new upload; poll calls `listSources` with current search query.
4. **source_cleanup**: `purge_orphans` guarded with `getattr` + `callable` before invoke.
5. **replaces_source_id UI**: Restored minimal form field wired to `uploadSource` options (single-file only).

## Verify

```bash
# Prerequisite: temporary stash of WIP admin_api/routes_wiki.py
git stash push -m "temp-final-fix-routes-wiki" -- admin_api/routes_wiki.py

pytest tests/test_source_upload_zip.py tests/test_source_tree_ops.py tests/test_upload_jobs.py tests/test_upload_resume.py -q --tb=short
```

```
......................                                                   [100%]
22 passed, 1 warning in 3.77s
```

```bash
git stash pop
```

```bash
# from web/
npm test -- --run src/pages/SourcesPage.test.tsx
```

```
✓ src/pages/SourcesPage.test.tsx (7 tests) 2498ms
Test Files  1 passed (1)
Tests  7 passed (7)
```

PASS — pytest **22 passed**; vitest **7 passed**.

## Commit
(one new commit on feat/async-upload — see git log)

## Concerns
- Pytest still requires stashing local WIP `admin_api/routes_wiki.py` (`build_wiki_compile_deps` import) for collection; unrelated to this fix commit.
