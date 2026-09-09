# Phase 2.2 Task 1 Report: evolution 模块 + KnowledgePort 扩展

**Status:** DONE  
**Date:** 2026-09-09  
**Baseline:** Phase 2.1 (`5d93f54`+)  
**Commit:** `feat: add evolution differ applier and knowledge as_of support`

## TDD Execution

| Step | Action | Result |
|------|--------|--------|
| 1 | Write `tests/test_evolution_differ.py`, `tests/test_evolution_applier.py` | Done |
| 2 | Run pytest — expect failures | Confirmed (module missing) |
| 3 | Implement `evolution/` + extend `KnowledgePort` / repos | Done |
| 4 | Full suite `pytest -v` | **50 passed, 19 skipped** |
| 5 | Commit | feat: add evolution differ applier and knowledge as_of support |

## Files Created

| File | Purpose |
|------|---------|
| `evolution/__init__.py` | 导出 `EvolutionService`, `KnowledgeDiffer`, `KnowledgeApplier`, ports |
| `evolution/ports.py` | `KnowledgeDiff`, `ApplyReport`, `EvolutionPort` |
| `evolution/family.py` | `family_key()` — 与 compiler `_family_id` 一致 |
| `evolution/differ.py` | `KnowledgeDiffer.diff_sources()` — 按 source + family 对齐 |
| `evolution/applier.py` | `KnowledgeApplier.apply_diff()` — supersede + activate staging |
| `evolution/service.py` | `EvolutionService` 门面实现 `EvolutionPort` |
| `tests/test_evolution_differ.py` | differ + family_key 测试 |
| `tests/test_evolution_applier.py` | applier + as_of + port 扩展测试 |

## Files Modified

| File | Change |
|------|--------|
| `knowledge/ports.py` | 新增 `mark_superseded`, `get_claims_for_source`, `get_claims_by_status`, `as_of` |
| `knowledge/memory_repo.py` | 实现上述 4 个方法 |
| `infra/pg_repos.py` | 实现 `get_claims_for_source`, `get_claims_by_status`, `as_of`（`mark_superseded` 已有） |
| `pyproject.toml` | 添加 `evolution*` 包 |

## API 示例

```python
from datetime import datetime, timezone

from evolution.differ import KnowledgeDiffer
from evolution.applier import KnowledgeApplier
from evolution.family import family_key
from knowledge.memory_repo import InMemoryKnowledge

repo = InMemoryKnowledge()
# ... seed old active + new staging claims ...

differ = KnowledgeDiffer(repo)
diff = differ.diff_sources("s-v3", "s-v4")
# diff.claims_superseded → [(old_id, staging_id)]

report = KnowledgeApplier(repo).apply_diff(diff)
# report.claims_activated, report.claims_superseded, report.events_created

fid = family_key("七天无理由", "运费承担方", "Concept")
claim_at_time = repo.as_of(datetime(2024, 3, 1, tzinfo=timezone.utc), fid)
```

## 核心行为

- **family 对齐**：`sha256(subject|predicate|object_type)[:16]`，与 `compiler.service._family_id` 相同
- **diff_sources**：old source 的 `active` claim 与 new source 的 `staging` claim 按 `family_id` 匹配；object/predicate 变更 → supersede 对；新 family → added
- **apply_diff**：`mark_superseded(old)` + 从 staging 追加 `version+1` 的 active claim；生成 event stub ID
- **as_of**：`valid_from <= t < valid_to`（`valid_to` 为 null 表示仍有效）；同 family 取最高 version

## Tests

```
pytest tests/test_evolution_differ.py tests/test_evolution_applier.py -v → 8 passed
pytest -v --ignore=web → 50 passed, 19 skipped
```

## Next Task

Task 2: `Source.replaces_source_id` + events 表 + staging 编译模式
