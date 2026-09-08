# Phase 2.1 Task 6 Report: require knowledge_base_id on ask and source API routes

**Status:** DONE  
**Date:** 2026-09-08  
**Baseline:** 25516e9  
**Commit:** feat: require knowledge_base_id on ask and source API routes

## TDD Execution

| Step | Action | Result |
|------|--------|--------|
| 1 | Update `tests/test_api.py` with `knowledge_base_id` from fixture / default kb | Done |
| 2 | Implement routes + deps factory | Done |
| 3 | Update `tests/test_e2e_sample.py` to use `build_orchestrator_for_kb(seeded_kb_id)` | Done |
| 4 | Full suite `pytest -v` | **30 passed, 15 skipped** |
| 5 | Commit | feat: require knowledge_base_id on ask and source API routes |

## Breaking API Changes

### POST /ask

```python
class AskRequest(BaseModel):
    knowledge_base_id: str  # required
    question: str
    session_id: str | None = None
```

Missing `knowledge_base_id` → HTTP 422.

### POST /sources

```python
class RegisterSourceRequest(BaseModel):
    knowledge_base_id: str  # required
    path: str
    type: str = "policy"
```

### POST /sources/{source_id}/compile

```python
class CompileSourceRequest(BaseModel):
    knowledge_base_id: str  # required (body)
```

### GET /claims/{claim_id}/evidence

Query param `knowledge_base_id` (required) scopes evidence lookup.

## Dependency Injection Refactor

| Before | After |
|--------|-------|
| `app.state.orchestrator` singleton via `build_default_orchestrator()` | Removed |
| `get_orchestrator(request)` | `build_orchestrator_for_request(kb_id, request)` |
| One global in-memory store | Per-`knowledge_base_id` cache on `app.state.orchestrator_cache` |

```python
# app/deps.py
def build_orchestrator_for_request(knowledge_base_id: str, request: Request) -> LangGraphOrchestrator:
    cache = request.app.state.orchestrator_cache
    if knowledge_base_id not in cache:
        cache[knowledge_base_id] = build_orchestrator_for_kb(knowledge_base_id)
    return cache[knowledge_base_id]
```

Cache keyed by `knowledge_base_id` ensures:
- In-memory mode: register → compile → ask share state within one app instance
- PG mode: repos already scoped by kb_id; cache avoids redundant wiring per request
- KB isolation: different `knowledge_base_id` values get separate orchestrator instances

## Files Modified

| File | Change |
|------|--------|
| `app/deps.py` | Factory `build_orchestrator_for_request` + `get_kb_repo` |
| `app/routes.py` | Required `knowledge_base_id` on ask/source/compile; query param on evidence |
| `app/main.py` | Drop singleton orchestrator; init `orchestrator_cache` |
| `tests/test_api.py` | `test_ask_requires_knowledge_base_id`, kb-scoped ingest/ask flow |
| `tests/test_e2e_sample.py` | `build_orchestrator_for_kb(seeded_kb_id)` |

## Example Request

```python
import httpx

kb_id = "default"  # InMemory; PG uses real uuid from admin API
client.post("/sources", json={
    "knowledge_base_id": kb_id,
    "path": "samples/refund_policy_v3.md",
    "type": "policy",
})
client.post(f"/sources/{source_id}/compile", json={"knowledge_base_id": kb_id})
resp = client.post("/ask", json={
    "knowledge_base_id": kb_id,
    "question": "定制商品能否七天无理由退货？",
})
```

## Tests

```
pytest tests/test_api.py tests/test_e2e_sample.py -v → 3 passed
pytest -v → 30 passed, 15 skipped
```

## Next Task

Task 7: admin API — knowledge base CRUD + source upload (`/admin/knowledge-bases/...`)
