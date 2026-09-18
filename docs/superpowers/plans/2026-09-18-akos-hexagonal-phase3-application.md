# AKOS Hexagonal Phase 3 — Application Layer Implementation Plan

> **For agentic workers:** Use executing-plans / subagent-driven-development. Checkbox steps.

**Goal:** Move use-case modules under `akos.application.{wiki,evolution,ingest,ask}` with legacy re-export shims.

**Architecture:** Application layer owns business workflows; adapters/ports stay where Phase 1–2 left them. Old import paths remain shims.

**Spec:** `docs/superpowers/specs/2026-09-17-akos-hexagonal-restructure-design.md`

## Map

| From | To |
|------|-----|
| `wiki/*.py` | `akos/application/wiki/` |
| `evolution/*.py` (except ports shim) | `akos/application/evolution/` |
| `compiler/*.py` (except ports shim) | `akos/application/ingest/` |
| `orchestrator/*.py` + `graphs/` (except ports shim) | `akos/application/ask/` |

## Constraints

- Preserve UTF-8 when copying (use Python `git show` / binary copy, not PowerShell `Set-Content`)
- Rewrite internal `from wiki.` / `from compiler.` / `from evolution.` / `from orchestrator.` to `akos.application.*` inside moved modules
- Leave `*/ports.py` as domain shims
- Identity smoke tests for key symbols

## Tasks

1. Scaffold `akos/application/`
2. Move wiki + shims + smoke
3. Move evolution + shims + smoke
4. Move compiler → ingest + shims + smoke
5. Move orchestrator → ask + shims + smoke
6. Regression subset + mark Phase 3 done + commit/push
