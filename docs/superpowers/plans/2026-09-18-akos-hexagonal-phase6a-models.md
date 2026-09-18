# AKOS Hexagonal Phase 6a + Domain Models

> **For agentic workers:** Checkbox steps. No legacy shims (Phase 5 policy).

**Goal:** Delete empty root shells; move `domains/` → `akos.domains`, `infra/bootstrap.py` → `akos.bootstrap`; move core dataclasses/errors into `akos.domain.models` / `akos.domain.errors`.

**Out of scope:** `knowledge` lint/topic, `infra` settings/db, `agents`, `verification`, `ontology`, moving `Hit`.

**Spec:** `docs/superpowers/specs/2026-09-17-akos-hexagonal-restructure-design.md`

## Map

| From | To |
|------|----|
| `evidence/`, `graph/` (empty) | delete |
| `domains/**` | `akos/domains/**` |
| `infra/bootstrap.py` | `akos/bootstrap.py` |
| `knowledge/models.py` | `akos/domain/models/knowledge.py` |
| `knowledge/errors.py` | `akos/domain/errors.py` |
| `knowledge_base/models.py` | `akos/domain/models/knowledge_base.py` |
| `memory/models.py` | `akos/domain/models/memory.py` |

## Tasks

1. Scaffold models + copy bootstrap/domains; rewrite imports; delete old paths / empty shells
2. Update `pyproject` includes, README package blurb, design §9
3. Regression (`AKOS_USE_PG=false`) + commit/push
