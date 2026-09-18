# AKOS Hexagonal Phase 2 — Adapters Home Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Move Port implementations (persistence, LLM, files, retrieval, neo4j) under `akos.adapters.*` with legacy re-export shims so behavior stays identical.

**Architecture:** Adapters implement `akos.domain.ports`; old import paths remain shims. `infra/bootstrap.py` and settings/db helpers may stay in `infra/` this phase (composition/config), but adapter modules relocate.

**Tech Stack:** Python 3.11+, pytest

**Spec:** `docs/superpowers/specs/2026-09-17-akos-hexagonal-restructure-design.md`

## Global Constraints

- Legacy imports must keep working (`from knowledge.memory_repo import InMemoryKnowledge`, etc.)
- Prefer `Hub is Shim` identity where practical (re-export same class object)
- Do not move compiler/wiki/orchestrator use cases (Phase 3)
- Do not move FastAPI/CLI (Phase 4)
- Keep `infra/settings.py`, `infra/db.py`, `infra/bootstrap.py`, `infra/schema_bootstrap.py` in place for now

## Target map

| From | To |
|------|-----|
| `knowledge/memory_repo.py` | `akos/adapters/persistence/knowledge_memory.py` |
| `evidence/memory_repo.py` | `akos/adapters/persistence/evidence_memory.py` |
| `graph/memory_repo.py` | `akos/adapters/persistence/graph_memory.py` |
| `memory/memory_repo.py` | `akos/adapters/persistence/memory_store.py` |
| `knowledge_base/pg_repo.py` | `akos/adapters/persistence/kb_pg.py` |
| `infra/pg_repos.py` | `akos/adapters/persistence/pg_knowledge.py` |
| `infra/pg_evidence.py` | `akos/adapters/persistence/pg_evidence.py` |
| `infra/pg_graph.py` | `akos/adapters/persistence/pg_graph.py` |
| `infra/pg_memory.py` | `akos/adapters/persistence/pg_memory.py` |
| `infra/pg_embeddings.py` | `akos/adapters/persistence/pg_embeddings.py` |
| `infra/llm.py` | `akos/adapters/llm/client.py` |
| `infra/files.py` | `akos/adapters/files/local.py` |
| `retrieval/*.py` (except ports shim) | `akos/adapters/retrieval/*.py` |
| `graph/adapters/neo4j.py` | `akos/adapters/graph/neo4j.py` |

---

### Task 1: Scaffold + persistence memory repos

**Files:** create `akos/adapters/**`; move four `memory_repo.py`; shim old paths; smoke test.

### Task 2: Move PG persistence adapters (+ kb pg_repo)

### Task 3: Move LLM + files adapters

### Task 4: Move retrieval package into adapters

### Task 5: Move neo4j adapter; update bootstrap imports to hub adapters (optional if shims suffice)

### Task 6: Regression tests + mark Phase 2 done in design spec + commit/push
