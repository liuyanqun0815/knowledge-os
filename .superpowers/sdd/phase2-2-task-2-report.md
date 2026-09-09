# Phase 2.2 Task 2 Report: Source.replaces + events + staging compile

**Status:** DONE  
**Date:** 2026-09-09  
**Baseline:** `9a0e8ce` (Phase 2.2 Task 1)  
**Commit:** `feat: add staging compile mode and policy v4 sample`

## TDD Execution

| Step | Action | Result |
|------|--------|--------|
| 1 | Write `tests/test_compiler_staging.py` | Done |
| 2 | Run pytest — expect failures | Confirmed (missing fields/methods) |
| 3 | Implement models, migration, repos, staging compile, v4 sample | Done |
| 4 | Full suite `pytest -v --ignore=web` | **55 passed, 19 skipped** |
| 5 | Commit | feat: add staging compile mode and policy v4 sample |

## Files Created

| File | Purpose |
|------|---------|
| `infra/migrations/003_evolution.sql` | `sources.replaces_source_id` + `events` 表 |
| `samples/refund_policy_v4.md` | v3 副本，运费承担方改为「平台」 |
| `tests/test_compiler_staging.py` | staging 编译、replaces、events 测试 |

## Files Modified

| File | Change |
|------|--------|
| `knowledge/models.py` | `Source.replaces_source_id: Optional[str] = None`（`Event` 已存在） |
| `knowledge/ports.py` | 新增 `append_event` / `list_events` |
| `knowledge/memory_repo.py` | 实现 events 存储与查询 |
| `infra/pg_repos.py` | `save_source` 含 replaces；`append_event` / `list_events` |
| `infra/schema.sql` | 同步 evolution 表结构 |
| `compiler/service.py` | `ingest(source_id, staging=False)`；staging 时 status=`staging`，不索引 retrieval |
| `compiler/ports.py` | `CompilerPort.ingest` 签名更新 |
| `tests/conftest.py` | PG fixture 运行 `003_evolution.sql` |

## API 示例

```python
from datetime import datetime, timezone

from compiler.service import KnowledgeCompiler
from knowledge.memory_repo import InMemoryKnowledge
from knowledge.models import Event, Source

# Source 演化链
src = Source(
    id="refund_policy_v4",
    title="退换货政策v4",
    type="policy",
    uri="samples/refund_policy_v4.md",
    version="4",
    created_at=datetime.now(timezone.utc),
    status="ready",
    replaces_source_id="refund_policy_v3",
)
repo.save_source(src)

# staging 编译：Claim 写入 status="staging"，不进入 active 检索
report = compiler.ingest("refund_policy_v4", staging=True)
staging = repo.get_claims_by_status("staging")

# 事件审计
repo.append_event(
    Event(
        id="evt-1",
        type="policy_changed",
        participants=["c-old", "c-new"],
        timestamp=datetime.now(timezone.utc),
        source_id="refund_policy_v4",
    )
)
events = repo.list_events(source_id="refund_policy_v4")
```

## 核心行为

- **Source.replaces_source_id**：可选字段，标记新文档替换的旧 source
- **events 表**：`(id, knowledge_base_id, type, participants, timestamp, source_id)`，按 kb 隔离
- **staging 编译**：`ingest(..., staging=True)` 写入 `status="staging"` 的 Claim；默认仍为 `active`
- **v4 样本**：与 v3 相同结构，仅「七天无理由退货运费承担方为**平台**」

## Tests

```
pytest tests/test_compiler_staging.py -v → 4 passed
pytest -v --ignore=web → 55 passed, 19 skipped
```

## Next Task

Task 3: LangGraph evolve 集成 ingest（`replaces_source_id` 触发 diff + apply）
