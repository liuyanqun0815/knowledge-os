# AKOS Hexagonal Phase 5 — Cleanup Implementation Plan

> **For agentic workers:** Use executing-plans / subagent-driven-development. Checkbox steps.

**Goal:** Remove legacy re-export shims; rewrite imports to `akos.*`; tighten `pyproject.toml` package includes; refresh README for the final layout.

**Architecture:** After Phase 1–4, only shims remain at old paths. Phase 5 makes `akos.*` the sole public Python surface for moved modules. Unmoved packages (`knowledge` models/lint, `infra` settings/bootstrap, `domains` plugins, `agents`, `verification` service, etc.) stay at repo root until later follow-ups.

**Tech Stack:** Python 3.11+, pytest

**Spec:** `docs/superpowers/specs/2026-09-17-akos-hexagonal-restructure-design.md`

## Global Constraints

- Rewrite `from X` / `import X` / `patch("X...")` strings for moved modules
- Do **not** move `infra/bootstrap.py` → `akos/bootstrap.py` or `domains/` → `akos/domains/` in this phase (spec lists them as eventual; optional follow-up)
- Delete pure-shim packages only after rewrites pass import smoke
- Preserve UTF-8 (Python scripts, not PowerShell Set-Content)

## Delete (pure shim trees / files)

| Delete | Replacement |
|--------|-------------|
| `app/`, `admin_api/` | `akos.interfaces.api*` |
| `compiler/`, `wiki/`, `orchestrator/`, `evolution/` | `akos.application.*` (+ ports → `akos.domain.ports.*`) |
| `retrieval/` | `akos.adapters.retrieval*` / `akos.domain.ports.retrieval` |
| `*/ports.py` shims, `*/memory_repo.py` shims, `infra/{llm,files,pg_*}.py`, `knowledge_base/pg_repo.py`, `graph/adapters/neo4j.py`, `domains/base.py` | hub paths |

## Keep at root (real code)

`knowledge/` (models, lint, …), `evidence/` (non-shim), `graph/` (if any non-shim left), `knowledge_base/models`, `memory/models`, `ontology/registry`, `verification/service`, `domains/*` plugins, `agents/`, `infra/` (settings, bootstrap, db, schema, upload, tracing, doc_extract)

## Tasks

1. Automated import rewrite across `akos/`, `tests/`, `agents/`, `domains/`, `infra/`, `knowledge/`, `scripts/`, …
2. Update hub identity tests (hub-only; drop shim asserts)
3. Delete shim trees/files; tighten `pyproject` `include` to `akos*` + remaining root packages
4. README + mark Phase 5 DONE in design spec
5. Regression (`AKOS_USE_PG=false`) + commit/push
