# Phase 2.1 Task 4 Report: PgGraph / PgEvidence / PgMemory（kb 作用域）

**Status:** DONE  
**Date:** 2026-09-08  
**Baseline:** 509ccaa  
**Commit:** feat: add scoped PostgreSQL graph evidence and memory adapters

## TDD Execution

| Step | Action | Result |
|------|--------|--------|
| 1 | Write `tests/test_pg_graph_evidence_memory.py` | Done |
| 2 | Implement `PgGraph`, `PgEvidence`, `PgMemory` | Done |
| 3 | Extend migration FK for graph/evidence/memory tables | Done |
| 4 | Run pytest | **29 passed, 15 skipped** (PG tests need `AKOS_USE_PG=true` + reachable DB) |
| 5 | Commit | feat: add scoped PostgreSQL graph evidence and memory adapters |

## Files Created

- `infra/pg_graph.py` — `PgGraph(engine, knowledge_base_id)` implements `GraphPort`
- `infra/pg_evidence.py` — `PgEvidence(engine, knowledge_base_id)` implements `EvidencePort`
- `infra/pg_memory.py` — `PgMemory(engine, knowledge_base_id)` implements `MemoryPort`
- `tests/test_pg_graph_evidence_memory.py` — upsert/query + cross-KB isolation tests

## Migration Extension

`infra/migrations/002_knowledge_bases.sql` (Task 2 already added `knowledge_base_id` columns):

- FK constraints: `entities`, `relations`, `claim_evidence`, `memory_episodes`, `memory_semantics` → `knowledge_bases(id)`
- Idempotent `DO $$ ... EXCEPTION WHEN duplicate_object` blocks

## API Example

```python
from infra.db import get_engine
from infra.pg_graph import PgGraph
from infra.pg_evidence import PgEvidence
from infra.pg_memory import PgMemory
from infra.settings import Settings

engine = get_engine(Settings(use_pg=True))
kb_id = "your-kb-uuid"

graph = PgGraph(engine, kb_id)
graph.upsert_entity("e_rule", "RefundRule", {"name": "七天无理由"})
edges = graph.neighbors("e_rule", predicates=["适用类目"])

evidence = PgEvidence(engine, kb_id)
evidence.bind("c1", "s1", TextSpan("s1", 0, 12, "定制商品不适用"), 0.95)
bundle = evidence.explain(["c1"])

memory = PgMemory(engine, kb_id)
memory.remember_episode("sess1", {"q": "能否退货", "a": "看类目"})
context = memory.recall("退货", "sess1")
```

## Scoped Query Pattern

All INSERT/SELECT filter by constructor-injected `knowledge_base_id`, mirroring `PgKnowledge`:

```python
repo = PgGraph(engine, knowledge_base_id="uuid-here")
repo.upsert_relation("e_rule", "适用类目", "e_cat", {})
repo.neighbors("e_rule")  # WHERE knowledge_base_id = :kb_id
```

## Tests

```
pytest tests/test_pg_graph_evidence_memory.py -v
# 6 tests: graph upsert/neighbors, evidence bind/explain, memory recall, 3× KB isolation

pytest -v  # 29 passed, 15 skipped (AKOS_USE_PG=false)
```

### PG Integration

```bash
psql $AKOS_DATABASE_URL -f infra/schema.sql
psql $AKOS_DATABASE_URL -f infra/migrations/002_knowledge_bases.sql
AKOS_USE_PG=true pytest tests/test_pg_graph_evidence_memory.py -v
```

Note: Local PG unavailable during this run (malformed `AKOS_DATABASE_URL` in `.env`); non-PG suite verified green.

## Fixture Fix

`tests/conftest.py`: `pg_engine` scope changed to `session` to match `pg_kb_repo` (fixes ScopeMismatch when `AKOS_USE_PG=true`).

## Integration (Task 5)

`infra/bootstrap.py` wires scoped adapters when `AKOS_USE_PG=true`:

```python
PgGraph(engine, knowledge_base_id)
PgEvidence(engine, knowledge_base_id)
PgMemory(engine, knowledge_base_id)
```

## Next Task

Task 6: require `knowledge_base_id` on ask and source API routes
