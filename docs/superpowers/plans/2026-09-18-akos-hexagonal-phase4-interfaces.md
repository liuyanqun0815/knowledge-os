# AKOS Hexagonal Phase 4 — Interfaces Implementation Plan

> **For agentic workers:** Use executing-plans / subagent-driven-development. Checkbox steps.

**Goal:** Move FastAPI (`app` + `admin_api`) under `akos.interfaces.api` with legacy re-export shims; update preferred entrypoints. CLI was subsequently **removed** (Web / Admin API only).

**Architecture:** Interfaces layer wires HTTP to application + bootstrap. Old import paths (`app.*`, `admin_api.*`) remain module-alias shims until Phase 5. Typer CLI (`cli/`, `akos.interfaces.cli`) is deleted.

**Tech Stack:** Python 3.11+, FastAPI, Typer, pytest

**Spec:** `docs/superpowers/specs/2026-09-17-akos-hexagonal-restructure-design.md`

## Global Constraints

- Preserve UTF-8 when copying (Python shutil / binary, not PowerShell `Set-Content`)
- Rewrite internal `from app.` / `from admin_api.` inside moved modules to `akos.interfaces.api*`
- Prefer `akos.application.*` for wiki/compiler/orchestrator imports inside moved modules where touched
- Keep `infra/bootstrap.py` / settings in place (composition root move is optional follow-up)
- Tests may keep `from app.main import create_app` via shims

## Target map

| From | To |
|------|----|
| `app/*.py` | `akos/interfaces/api/*.py` |
| `admin_api/*.py` | `akos/interfaces/api/admin_api/*.py` |
| `cli/main.py` | `akos/interfaces/cli/main.py` |

## Preferred entrypoints (update + keep shim)

| Role | New | Shim still works |
|------|-----|------------------|
| uvicorn | `akos.interfaces.api.main:app` | `app.main:app` |
| CLI script | `akos.interfaces.cli.main:app` | `cli.main:app` |

## Tasks

### Task 1: Scaffold + move API packages

- [ ] Create `akos/interfaces/{__init__,api/__init__,api/admin_api/,cli/__init__}.py`
- [ ] Copy `app/*.py` → `akos/interfaces/api/`
- [ ] Copy `admin_api/*.py` → `akos/interfaces/api/admin_api/`
- [ ] Rewrite imports inside moved tree
- [ ] Replace root `app/` and `admin_api/` modules with sys.modules shims
- [ ] Smoke: `from app.main import create_app`; identity with hub

### Task 2: Move CLI

- [ ] Copy `cli/main.py` → `akos/interfaces/cli/main.py`; rewrite imports
- [ ] Shim `cli/main.py`
- [ ] Update `pyproject.toml` `[project.scripts]` to new path (shim remains)

### Task 3: Entrypoints / Docker / docs

- [ ] Update `Dockerfile`, `deploy/docker-compose.dev.yml`, `README.md` (and `web/README.md` if present) to preferred uvicorn path
- [ ] Mark Phase 4 done in design spec

### Task 4: Regression + commit/push

- [ ] `pytest` subset: admin/source/ask API tests + import smoke
- [ ] Commit + push (same cadence as Phase 1–3)
