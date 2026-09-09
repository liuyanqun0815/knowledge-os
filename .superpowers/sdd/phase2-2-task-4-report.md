# Phase 2.2 Task 4 Report: as_of Time Query in ask flow

**Status:** DONE  
**Date:** 2026-09-09  
**Baseline:** Phase 2.2 Task 3 (LangGraph evolve ingest)  
**Commit:** `feat: add as_of time query to ask LangGraph pipeline`

## TDD Execution

| Step | Action | Result |
|------|--------|--------|
| 1 | Write `tests/test_as_of_query.py` | Done |
| 2 | Run pytest — expect failure before wiring | Confirmed |
| 3 | Extend Answer, AskState, nodes, graph, service, routes, retrieval | Done |
| 4 | Full suite `pytest -v --ignore=web` | **66 passed, 19 skipped** |
| 5 | Commit | feat: add as_of time query to ask LangGraph pipeline |

## Files Modified

| File | Change |
|------|--------|
| `knowledge/models.py` | `Answer.as_of: datetime \| None` |
| `orchestrator/state.py` | `AskState.as_of` |
| `orchestrator/nodes.py` | `parse_time_node`; `retrieve`/`explain`/`answer` 时序过滤；evolve 后索引新 claim |
| `orchestrator/graphs/ask_graph.py` | `recall → parse_time → normalize → …` |
| `orchestrator/service.py` | `ask(..., as_of=)`；`evolve_source` 索引激活 claim |
| `app/routes.py` | 传递 `body.as_of`；`AskResponse.as_of` |
| `retrieval/hybrid.py` | `filters["as_of"]` 按 `valid_from/valid_to` 过滤 |
| `tests/test_orchestrator_graph.py` | invoke 初始 state 含 `as_of` |

## Files Created

| File | Purpose |
|------|---------|
| `tests/test_as_of_query.py` | v3→v4 后 `as_of(v3日)` 返回买家；问句时间解析 |

## ask_graph 拓扑

```text
recall → parse_time → normalize → route_mode → retrieve → explain → answer → remember → END
```

- **parse_time**：请求体 `as_of` 优先；否则解析 `2024`/`2024年` → 年中；`当时/那时/之前` → 去年年中
- **retrieve**：`filters["as_of"]` 传给 HybridRetrieval
- **explain**：命中 claim 按 family 用 `knowledge.as_of()` 解析历史版本
- **answer**：回填 `Answer.as_of`

## API 示例

```python
from datetime import datetime, timezone
from infra.bootstrap import build_orchestrator_for_kb

orch = build_orchestrator_for_kb("default")
orch.ingest("samples/refund_policy_v3.md", "policy")
v3_claim = orch.deps.knowledge.get_active_claims("七天无理由", "运费承担方")[0]
as_of_time = v3_claim.valid_from

orch.ingest("samples/refund_policy_v4.md", "policy", replaces_source_id="refund_policy_v3")

# 当前政策
current = orch.ask("七天无理由退货运费承担方是谁？")
assert "平台" in current.text

# 历史时点
historical = orch.ask("七天无理由退货运费承担方是谁？", as_of=as_of_time)
assert "买家" in historical.text
assert historical.as_of == as_of_time
```

HTTP:

```json
POST /ask
{
  "knowledge_base_id": "default",
  "question": "七天无理由退货运费承担方是谁？",
  "as_of": "2024-01-01T00:00:00+00:00"
}
```

## 验收结果

1. v3→v4 evolve 后，无 `as_of` 问句返回 **平台**
2. `as_of(v3 valid_from)` 返回 **买家**（非平台）
3. `Answer.as_of` 与请求/解析时间一致
4. Phase 2.2 E2E（`test_evolution_e2e.py`）全部通过

## Tests

```
pytest tests/test_as_of_query.py -v → 4 passed
pytest tests/test_evolution_e2e.py -v → 4 passed
pytest -v --ignore=web → 66 passed, 19 skipped
```

## Next Task

Task 5: API + admin evolve + claim history（`routes_evolution.py`、GET claim history）
