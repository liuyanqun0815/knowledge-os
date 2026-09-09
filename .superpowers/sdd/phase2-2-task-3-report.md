# Phase 2.2 Task 3 Report: LangGraph evolve 集成 ingest

**Status:** DONE  
**Date:** 2026-09-09  
**Baseline:** Phase 2.2 Task 2 (staging 编译 + `Source.replaces_source_id`)  
**Commit:** `feat: integrate evolution into LangGraph ingest pipeline`

## TDD Execution

| Step | Action | Result |
|------|--------|--------|
| 1 | Write `tests/test_evolve_ingest.py` | Done |
| 2 | Run pytest — expect failure before wiring | Confirmed (missing evolve node) |
| 3 | Extend `IngestState`, nodes, graph, service, bootstrap | Done |
| 4 | Full suite `pytest -v --ignore=web` | **55 passed, 19 skipped** |
| 5 | Commit | feat: integrate evolution into LangGraph ingest pipeline |

## Files Modified

| File | Change |
|------|--------|
| `orchestrator/state.py` | `IngestState` 增 `replaces_source_id`、`evolve_report`（可选） |
| `orchestrator/nodes.py` | `store_source_node` 写入 replaces；`compile_node` staging 模式；新增 `evolve_node` |
| `orchestrator/graphs/ingest_graph.py` | `store → compile → [replaces?] evolve → END` 条件边 |
| `orchestrator/service.py` | `register_source` / `ingest(..., replaces_source_id=)` |
| `infra/bootstrap.py` | `OrchestratorDeps.evolution: EvolutionService` |

## Files Created

| File | Purpose |
|------|---------|
| `tests/test_evolve_ingest.py` | v3 正常 ingest → v4 replaces v3 → 运费承担方 supersede |

## ingest_graph 拓扑

```text
store → compile → [replaces_source_id?] → evolve → END
                      ↓ (无 replaces)
                     END
```

- **compile**：`replaces_source_id` 存在时 `compiler.ingest(source_id, staging=True)`
- **evolve**：`EvolutionService.diff_sources(old, new)` → `apply_diff`

## API 示例

```python
from infra.bootstrap import build_orchestrator_for_kb

orch = build_orchestrator_for_kb("default")

# 正常 ingest v3
orch.ingest("samples/refund_policy_v3.md", "policy")

# v4 替换 v3，自动 diff + supersede
orch.ingest(
    "samples/refund_policy_v4.md",
    "policy",
    replaces_source_id="refund_policy_v3",
)

freight = orch.deps.knowledge.get_active_claims("七天无理由", "运费承担方")
assert freight[0].object == "平台"
```

## 验收结果

1. ingest v3 → active 运费承担方 = **买家**
2. ingest v4 with `replaces_source_id=refund_policy_v3` → active 运费承担方 = **平台**
3. 旧 claim `status=superseded`，新 claim `version=2`
4. v4 Source 持久化 `replaces_source_id`

## Tests

```
pytest tests/test_evolve_ingest.py -v → 1 passed
pytest -v --ignore=web → 55 passed, 19 skipped
```

## Next Task

Task 4: as_of Time Query + `Answer.as_of`（`ask_graph` parse_time + 过滤）
