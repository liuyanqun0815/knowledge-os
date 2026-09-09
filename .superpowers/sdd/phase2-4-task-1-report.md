# Phase 2.4 Task 1 Report: Neo4j GraphPort with kb_id isolation

**Status:** DONE  
**Date:** 2026-09-09  
**Spec:** `docs/superpowers/specs/2026-09-08-akos-phase2-design.md` §8.1  
**Commit:** feat: add Neo4j GraphPort adapter with kb_id isolation

## TDD Execution

| Step | Action | Result |
|------|--------|--------|
| 1 | Write `tests/test_neo4j_graph.py` | Done |
| 2 | Implement settings, Neo4jGraph, bootstrap `_build_graph` | Done |
| 3 | Run `pytest tests/test_neo4j_graph.py -v` | **1 passed, 1 skipped** |
| 4 | Full suite `pytest -v` | **83 passed, 20 skipped** |
| 5 | Commit | feat: add Neo4j GraphPort adapter with kb_id isolation |

## Files Created

- `graph/adapters/__init__.py` — adapter package marker
- `graph/adapters/neo4j.py` — `Neo4jGraph` implementing GraphPort with lazy driver connect
- `tests/test_neo4j_graph.py` — InMemory always runs; Neo4j integration skip unless env

## Files Modified

- `infra/settings.py` — `graph_backend`, `neo4j_uri`, `neo4j_user`, `neo4j_password`
- `infra/bootstrap.py` — `_build_graph(settings, engine, kb_id)` selects InMemory / PgGraph / Neo4jGraph
- `pyproject.toml` — optional `[neo4j]` extra: `neo4j>=5.0.0`

## Graph Backend Selection

| `AKOS_GRAPH_BACKEND` | `AKOS_USE_PG` | Implementation |
|----------------------|---------------|----------------|
| `memory` (default) | any | `InMemoryGraph` |
| `postgres` | `true` | `PgGraph` |
| `neo4j` | any | `Neo4jGraph` |

## Neo4j kb_id Isolation

- Entity nodes: `MERGE (n:Entity {id, kb_id})`
- Relations: `MERGE (src)-[r:RELATES_TO {predicate, kb_id}]->(dst)`
- Neighbors query filters both node and relationship by `kb_id`; depth=1 only

## Usage Example

```python
from graph.adapters.neo4j import Neo4jGraph

graph = Neo4jGraph(
    uri="bolt://localhost:7687",
    user="neo4j",
    password="akos-neo4j",
    knowledge_base_id="my-kb-id",
)
graph.upsert_entity("e_rule", "RefundRule", {"name": "七天无理由"})
graph.upsert_relation("e_rule", "适用类目", "e_cat", {})
edges = graph.neighbors("e_rule", predicates=["适用类目"])
graph.close()
```

## Neo4j Integration Test

Set env and install optional dep:

```bash
pip install -e ".[neo4j]"
export AKOS_NEO4J_URI=bolt://localhost:7687
export AKOS_GRAPH_BACKEND=neo4j
pytest tests/test_neo4j_graph.py::test_neo4j_graph_upsert_and_neighbors -v
```

## Notes

- Default `graph_backend=memory` preserves Phase 2.1–2.3 behavior (InMemoryGraph even when `use_pg=true`)
- PG graph tests still instantiate `PgGraph` directly; bootstrap PG graph requires `AKOS_GRAPH_BACKEND=postgres`
