# Phase 2.2 Task 5 Report: API evolve + claim history endpoints

**Status:** DONE  
**Date:** 2026-09-09  
**Baseline:** Phase 2.2 Task 4 (as_of Time Query)  
**Commit:** `feat: add evolution and claim history API routes`

## TDD Execution

| Step | Action | Result |
|------|--------|--------|
| 1 | Write `tests/test_evolution_api.py` | Done |
| 2 | Run pytest — expect failure before routes | Confirmed |
| 3 | Add admin/public routes, schemas, orchestrator `evolve_source` | Done |
| 4 | Full suite `pytest -v --ignore=web` | **66 passed, 19 skipped** |
| 5 | Commit | feat: add evolution and claim history API routes |

## Files Created

| File | Purpose |
|------|---------|
| `admin_api/routes_evolution.py` | POST evolve + admin claim history |
| `admin_api/claim_history.py` | Shared timeline helper (excludes staging) |
| `tests/test_evolution_api.py` | Upload/replaces, manual evolve, public history |

## Files Modified

| File | Change |
|------|--------|
| `admin_api/schemas.py` | `EvolveSourceRequest/Response`, `ClaimHistoryItemResponse` |
| `admin_api/routes_sources.py` | Upload form `replaces_source_id` → `ingest(...)` |
| `admin_api/__init__.py` | Export `evolution_router` |
| `app/main.py` | Mount evolution router under `/admin` |
| `app/routes.py` | `RegisterSourceRequest.replaces_source_id`; GET `/claims/{family_id}/history` |
| `orchestrator/service.py` | `evolve_source()`; `compile_source` uses staging when replaces set |

## API Routes

| Method | Path | Description |
|--------|------|-------------|
| POST | `/admin/knowledge-bases/{kb_id}/sources/{source_id}/evolve` | diff + apply on staged source |
| GET | `/admin/knowledge-bases/{kb_id}/claims/{family_id}/history` | Version timeline (admin) |
| GET | `/claims/{family_id}/history?knowledge_base_id=` | Version timeline (public) |

Upload and register also accept optional `replaces_source_id` for one-shot ingest evolve.

## API 示例

```python
import httpx
from evolution.family import family_key

kb_id = "default"
freight_family = family_key("七天无理由", "运费承担方", "Concept")

# 上传 v4 并替换 v3（自动 ingest evolve）
with open("samples/refund_policy_v4.md", "rb") as f:
    httpx.post(
        f"/admin/knowledge-bases/{kb_id}/sources/upload",
        files={"file": ("refund_policy_v4.md", f)},
        data={"replaces_source_id": "refund_policy_v3"},
    )

# 或分步：register → compile(staging) → evolve
httpx.post(
    "/sources",
    json={
        "knowledge_base_id": kb_id,
        "path": "samples/refund_policy_v4.md",
        "replaces_source_id": "refund_policy_v3",
    },
)
httpx.post(f"/sources/refund_policy_v4/compile", json={"knowledge_base_id": kb_id})
httpx.post(f"/admin/knowledge-bases/{kb_id}/sources/refund_policy_v4/evolve", json={})

# Claim 版本时间线
history = httpx.get(
    f"/claims/{freight_family}/history",
    params={"knowledge_base_id": kb_id},
).json()
assert len(history) == 2
assert history[0]["object"] == "买家"
assert history[1]["object"] == "平台"
```

## 核心行为

- **evolve 端点**：新 source 需有 `replaces_source_id`；若无 staging claim 则先 staging 编译，再 diff + apply
- **claim history**：按 `version` 升序；过滤 `status=staging` 中间态
- **upload/register**：可选 `replaces_source_id` 触发 ingest 图完整 evolve 流程

## Tests

```
pytest tests/test_evolution_api.py -v → 3 passed
pytest -v --ignore=web → 66 passed, 19 skipped
```

## Next Task

Task 6: E2E v3→v4 + 验收（`tests/test_evolution_e2e.py`, README）
