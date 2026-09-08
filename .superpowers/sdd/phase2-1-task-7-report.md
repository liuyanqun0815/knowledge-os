# Phase 2.1 Task 7 Report: admin_api KB CRUD + source upload

**Status:** DONE  
**Date:** 2026-09-08  
**Baseline:** 69ce7b9 (Task 6 — require knowledge_base_id on ask)  
**Commit:** feat: add admin API for knowledge bases and source upload

## TDD Execution

| Step | Action | Result |
|------|--------|--------|
| 1 | Test create kb → upload md → list sources → claims > 0 | Done |
| 2 | Implement admin routes + mount at `/admin` | Done |
| 3 | Add `list_sources` to KnowledgePort | Done |
| 4 | Full suite `pytest -v` | **35 passed, 17 skipped** |
| 5 | Commit | feat: add admin API for knowledge bases and source upload |

## Files Created / Modified

| File | Change |
|------|--------|
| `admin_api/__init__.py` | Package exports |
| `admin_api/schemas.py` | Request/response Pydantic models |
| `admin_api/deps.py` | `require_kb_repo` with admin token guard |
| `admin_api/routes_knowledge_bases.py` | POST/GET/PATCH `/admin/knowledge-bases*` |
| `admin_api/routes_sources.py` | Upload + list sources per kb |
| `app/main.py` | Mount admin routers at `/admin` |
| `app/admin_auth.py` | Optional `X-Admin-Token` guard (used by admin router) |
| `knowledge/ports.py` | `list_sources()` on KnowledgePort |
| `knowledge/memory_repo.py` | In-memory `list_sources` |
| `infra/pg_repos.py` | PG `list_sources` scoped by kb |
| `tests/test_admin_kb_api.py` | In-memory upload + PG CRUD flow |

## Admin API Routes

| Method | Path | Description |
|--------|------|-------------|
| POST | `/admin/knowledge-bases` | Create kb (requires PG) |
| GET | `/admin/knowledge-bases` | List kbs |
| GET | `/admin/knowledge-bases/{id}` | Get kb detail |
| PATCH | `/admin/knowledge-bases/{id}` | Update fields or archive (`status=archived`) |
| POST | `/admin/knowledge-bases/{id}/sources/upload` | Multipart upload → save under `AKOS_DATA_ROOT/{kb_id}/` → `ingest` |
| GET | `/admin/knowledge-bases/{id}/sources` | List sources in kb |

## Upload Flow

```python
# Saved path: {AKOS_DATA_ROOT}/{kb_id}/{filename}
orchestrator = build_orchestrator_for_request(kb_id, request)
report = orchestrator.ingest(str(dest_path), source_type)
# report.claims_created >= 1 for samples/refund_policy_v3.md
```

## Example Usage

```python
from fastapi.testclient import TestClient
from app.main import create_app

client = TestClient(create_app(data_root="./data"))

# Create kb (PG only)
kb = client.post(
    "/admin/knowledge-bases",
    json={"name": "电商库", "domain_type": "ecommerce_cs", "description": ""},
).json()

# Upload policy markdown
with open("samples/refund_policy_v3.md", "rb") as f:
    upload = client.post(
        f"/admin/knowledge-bases/{kb['id']}/sources/upload",
        files={"file": ("refund_policy_v3.md", f, "text/markdown")},
        data={"source_type": "policy"},
    )
assert upload.json()["claims_created"] >= 1

sources = client.get(f"/admin/knowledge-bases/{kb['id']}/sources")
assert len(sources.json()) >= 1
```

## Tests

```
pytest tests/test_admin_kb_api.py -v
# 1 passed (in-memory), 2 skipped (PG) when AKOS_USE_PG=false

pytest -v
# 35 passed, 17 skipped
```

## Notes

- CRUD endpoints return **503** when `AKOS_USE_PG=false` (no `PgKnowledgeBaseRepo`).
- Upload/list work in in-memory mode using synthetic kb (`default`).
- When `ADMIN_API_TOKEN` is set, admin routes require matching `X-Admin-Token` header (401 before repo checks).
- Archived kbs reject further uploads with **400**.

## Next

Task 8: CLI `--kb` flag for persistent cross-command usage.
