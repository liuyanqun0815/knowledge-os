# Phase 2.4 Task 4 Report — admin_api 完善

**Baseline:** Phase 2.4 Task 3 (Procedural Memory)

**Commit:** `feat: extend admin API for claims quarantine and debug`

## Summary

Extended admin API per spec §8.3 with claims listing, quarantine management (list + approve), and debug endpoints (ask with trace, graph neighbors). Extended `KnowledgePort` with `approve_quarantine` and enriched `list_quarantine` to return stable `id` fields for approval.

## Files created

| File | Purpose |
|------|---------|
| `admin_api/routes_claims.py` | `GET /admin/knowledge-bases/{kb_id}/claims?status=&subject=` |
| `admin_api/routes_quarantine.py` | `GET .../quarantine`, `POST .../quarantine/{id}/approve` |
| `admin_api/routes_debug.py` | `POST .../debug/ask`, `GET .../debug/graph/{entity_id}/neighbors` |
| `admin_api/claim_helpers.py` | Claim filtering + post-approve graph/retrieval indexing |
| `tests/test_admin_phase24.py` | 6 tests: quarantine list, approve, claims filter, debug ask/graph |

## Files modified

| File | Change |
|------|--------|
| `knowledge/ports.py` | Added `approve_quarantine(quarantine_id: int) -> Claim` |
| `knowledge/memory_repo.py` | Stable quarantine ids; approve creates/reactivates claims |
| `infra/pg_repos.py` | `list_quarantine` returns DB `id`; `approve_quarantine` with DELETE + claim upsert |
| `admin_api/schemas.py` | ClaimList, Quarantine, DebugAsk, GraphNeighbor response models |
| `app/main.py` | Register claims, quarantine, debug routers under `/admin` |

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/admin/knowledge-bases/{kb_id}/claims` | Filter by `status`, `subject` |
| GET | `/admin/knowledge-bases/{kb_id}/quarantine` | List quarantine items with `id` |
| POST | `/admin/knowledge-bases/{kb_id}/quarantine/{quarantine_id}/approve` | Approve → active claim, remove from quarantine |
| POST | `/admin/knowledge-bases/{kb_id}/debug/ask` | Ask with full trace (always) |
| GET | `/admin/knowledge-bases/{kb_id}/debug/graph/{entity_id}/neighbors` | Graph subgraph query |

Claim history remains at `GET /admin/knowledge-bases/{kb_id}/claims/{family_id}/history` (Task 2.2 evolution router).

## approve_quarantine behavior

1. **`invalid_predicate` raw** (compiler): creates new `active` claim from `subject/predicate/object` fields.
2. **`span_mismatch` raw** (verify): reactivates existing claim by `claim_id`.
3. On success: removes quarantine row; route handler indexes claim in graph + retrieval.

## Verification

```bash
pytest tests/test_admin_phase24.py -v
# 6 passed
```

## Next

- Task 5: Adapter parity tests + CLI AnswerV2 fields
- Task 6: Phase 2.4 E2E acceptance (quarantine approve → main graph)
