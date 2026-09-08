# Phase 2.1 Task 2 Report: knowledge_base_id 迁移 + PgKnowledge 作用域

**Status:** DONE  
**Date:** 2026-09-08  
**Baseline:** 5336c55  
**Commit:** feat: scope PostgreSQL knowledge repository by knowledge_base_id

## TDD Execution

| Step | Action | Result |
|------|--------|--------|
| 1 | Write `tests/test_kb_isolation.py` | Done |
| 2 | Extend migration + scoped `PgKnowledge` | Done |
| 3 | Update `infra/schema.sql` for fresh installs | Done |
| 4 | Run pytest | **28 passed, 9 skipped** (PG tests need `AKOS_USE_PG=true`) |
| 5 | Commit | feat: scope PostgreSQL knowledge repository by knowledge_base_id |

## Changes

### Migration (`infra/migrations/002_knowledge_bases.sql`)

- Seeds `legacy` knowledge base for existing Phase 1 rows
- Adds `knowledge_base_id NOT NULL` to: `sources`, `source_texts`, `claims`, `quarantine`, plus prep columns on `entities`, `relations`, `claim_evidence`, `memory_*`
- Creates indexes and FK constraints (idempotent `DO $$ ... EXCEPTION` blocks)

### Fresh schema (`infra/schema.sql`)

- Includes `knowledge_bases` table and `knowledge_base_id` on all business tables
- `memory_semantics` unique key scoped to `(knowledge_base_id, key)`

### PgKnowledge (`infra/pg_repos.py`)

```python
repo = PgKnowledge(engine, knowledge_base_id="uuid-here")
repo.append_claim(claim)  # INSERT includes knowledge_base_id
repo.get_active_claims("七天无理由")  # WHERE knowledge_base_id = :kb_id
```

All INSERT/SELECT/UPDATE on `sources`, `source_texts`, `claims`, `quarantine` filtered by constructor-injected `knowledge_base_id`.

### Tests

- `tests/test_kb_isolation.py` — claims, sources, quarantine do not leak across two KBs
- Shared PG fixtures moved to `tests/conftest.py`
- `tests/test_pg_knowledge.py` — creates per-test KB via `pg_knowledge` fixture

### Bootstrap interim

`build_pg_knowledge(knowledge_base_id="legacy")` keeps Phase 1 PG path working until Task 5 `build_orchestrator_for_kb`.

## PG Integration Test Command

```bash
psql $AKOS_DATABASE_URL -f infra/schema.sql
psql $AKOS_DATABASE_URL -f infra/migrations/002_knowledge_bases.sql
AKOS_USE_PG=true pytest tests/test_kb_isolation.py tests/test_pg_knowledge.py -v
```

Note: Local Docker PG unavailable during this run; non-PG suite verified green.

## Next Task

Task 3: DomainPort + 领域注册表 (already partially present in working tree from parallel work)
