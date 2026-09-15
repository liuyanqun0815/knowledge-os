# Task 3 Report: Schema + routes return 202

**Branch:** `feat/async-upload`  
**Date:** 2026-09-15

## Status

✅ Complete — TDD green, committed.

## Changes

| File | Action |
|------|--------|
| `admin_api/schemas.py` | Added `accepted_async: bool = False` to `SourceUploadResponse` |
| `admin_api/routes_sources.py` | Accept-only uploads; schedule `process_uploaded_source`; HTTP 202 |
| `app/deps.py` | Pass `request.app.state.settings` into orchestrator build |
| `infra/bootstrap.py` | `build_orchestrator_for_kb(..., settings=None)` |
| `tests/test_source_upload_zip.py` | 202 / bad-suffix / extract-failure coverage; 200→202 |
| `tests/test_source_tree_ops.py` | Upload asserts → 202 + `accepted_async` |
| `tests/test_upload_ingest_summary.py` | Accept message; claims via later GET |
| `tests/test_hybrid_extraction_api.py` | Expect `process_uploaded_source` schedule |
| Other upload setup tests | `status_code` 200→202; claims via GET where needed |

## Interfaces Delivered

```python
def _schedule_upload_processing(
    kb_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    kb_dir: Path,
    originals: list[Path],
    source_type: str,
    replaces_source_id: str | None = None,
) -> list[ZipUploadItemResponse]: ...
```

- Upload / upload-tree / upload-zip: `status_code=202`, `accepted_async=True`
- Response counters start at 0; `ingest_summary="已接收，后台编译中"`
- `replaces_source_id` only when `len(originals)==1`

## TDD Evidence

### RED (Step 2)

```
pytest tests/test_source_upload_zip.py::test_upload_md_returns_202_accepted_async -q --tb=short
F                                                                        [100%]
assert 200 == 202
1 failed in 1.73s
```

### GREEN (Step 6)

```
pytest tests/test_source_upload_zip.py tests/test_source_tree_ops.py tests/test_upload_jobs.py tests/test_upload_ingest_summary.py -q --tb=short
.......................                                                  [100%]
23 passed in 3.77s
```

## Test Summary

| Suite | Result |
|-------|--------|
| `test_source_upload_zip` + tree + upload_jobs + ingest_summary | 23 passed |
| `test_hybrid_extraction_api` (related) | 4 passed |

## Self-Review

**Good:**
- No in-request ingest; enrichment lives inside `process_uploaded_source`
- Validation/save failures still 4xx; accept path always 202
- Starlette TestClient note honored: post-202 status may already be non-pending

**Concern:**
- Nested uploads required passing app `settings`/`data_root` into `build_orchestrator_for_kb`; without it pending id (`docs__guide`) diverged from ingest stem id (`guide`)

## Commit

`feat: accept all source uploads asynchronously with 202`
