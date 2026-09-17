# AKOS Hexagonal Phase 1 — Port Hub Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Centralize all Port Protocols (and colocated DTOs currently defined in `*/ports.py`) under `akos.domain.ports`, with backward-compatible re-exports at the old paths so behavior and imports stay green.

**Architecture:** Create `akos/domain/ports/` as the single source of truth for Protocols. Legacy modules become one-line / short re-export shims. No adapter or use-case moves in this phase.

**Tech Stack:** Python 3.11+, setuptools package layout, pytest

**Spec:** `docs/superpowers/specs/2026-09-17-akos-hexagonal-restructure-design.md`

## Global Constraints

- Keep all existing public import paths working (`from knowledge.ports import KnowledgePort`, etc.)
- Do not change Protocol method signatures
- Do not move `memory_repo` / `pg_repos` / LangGraph nodes in this phase
- `pytest` must pass after every task commit
- black line length 120; snake_case modules

## File map (Phase 1)

| Create | Role |
|--------|------|
| `akos/__init__.py` | Package root |
| `akos/domain/__init__.py` | Domain layer marker |
| `akos/domain/ports/__init__.py` | Re-export commonly used Ports |
| `akos/domain/ports/knowledge.py` | from `knowledge/ports.py` |
| `akos/domain/ports/evidence.py` | from `evidence/ports.py` |
| `akos/domain/ports/graph.py` | from `graph/ports.py` |
| `akos/domain/ports/memory.py` | from `memory/ports.py` |
| `akos/domain/ports/ontology.py` | from `ontology/ports.py` |
| `akos/domain/ports/knowledge_base.py` | from `knowledge_base/ports.py` |
| `akos/domain/ports/compiler.py` | from `compiler/ports.py` (incl. ExtractedClaim DTOs) |
| `akos/domain/ports/retrieval.py` | from `retrieval/ports.py` (incl. Hit, RetrievalMode) |
| `akos/domain/ports/evolution.py` | from `evolution/ports.py` |
| `akos/domain/ports/verification.py` | from `verification/ports.py` |
| `akos/domain/ports/orchestrator.py` | from `orchestrator/ports.py` |
| `akos/domain/ports/domain.py` | `DomainPort` from `domains/base.py` |

| Modify | Role |
|--------|------|
| Each legacy `*/ports.py` + `domains/base.py` | Shim re-export |
| `pyproject.toml` | Add `akos*` to `packages.find.include` |
| `tests/test_port_hub_imports.py` | New smoke tests for old + new import paths |

---

### Task 1: Scaffold `akos.domain.ports` and move KnowledgePort

**Files:**
- Create: `akos/__init__.py`, `akos/domain/__init__.py`, `akos/domain/ports/__init__.py`
- Create: `akos/domain/ports/knowledge.py` (copy body of `knowledge/ports.py`)
- Modify: `knowledge/ports.py` → re-export from `akos.domain.ports.knowledge`
- Modify: `pyproject.toml` — add `"akos*"` to include list
- Test: `tests/test_port_hub_imports.py`

**Interfaces:**
- Consumes: existing `knowledge/ports.py` Protocol body
- Produces: `akos.domain.ports.knowledge.KnowledgePort`; shim `knowledge.ports.KnowledgePort`

- [ ] **Step 1: Write failing import smoke test**

```python
# tests/test_port_hub_imports.py
def test_knowledge_port_importable_from_hub_and_shim():
    from akos.domain.ports.knowledge import KnowledgePort as Hub
    from knowledge.ports import KnowledgePort as Shim
    assert Hub is Shim
```

- [ ] **Step 2: Run test — expect FAIL (no `akos` package)**

```bash
pytest tests/test_port_hub_imports.py -v
```

- [ ] **Step 3: Create package scaffolding + move KnowledgePort + shim + pyproject**

- [ ] **Step 4: Run test — expect PASS**

```bash
pytest tests/test_port_hub_imports.py -v
```

- [ ] **Step 5: Commit**

```bash
git add akos knowledge/ports.py pyproject.toml tests/test_port_hub_imports.py
git commit -m "refactor: add akos.domain.ports hub and move KnowledgePort"
```

---

### Task 2: Move remaining storage / ontology ports

**Files:**
- Create: `akos/domain/ports/{evidence,graph,memory,ontology,knowledge_base}.py`
- Modify: corresponding legacy `*/ports.py` → shims
- Modify: `tests/test_port_hub_imports.py` — assert `Hub is Shim` for each

**Interfaces:**
- Produces: hub modules + shims for EvidencePort, GraphPort, MemoryPort, OntologyPort, KnowledgeBasePort (and colocated DTOs)

- [ ] **Step 1: Extend smoke test for the five modules (fail first if desired, or add after move in same commit if copying verbatim)**

- [ ] **Step 2: Move bodies + replace legacy with re-exports**

- [ ] **Step 3: `pytest tests/test_port_hub_imports.py tests/test_knowledge.py tests/test_pg_knowledge.py -v`**

- [ ] **Step 4: Commit**

```bash
git commit -m "refactor: move evidence/graph/memory/ontology/kb ports into hub"
```

---

### Task 3: Move compiler + retrieval ports (DTO-heavy)

**Files:**
- Create: `akos/domain/ports/compiler.py`, `akos/domain/ports/retrieval.py`
- Modify: `compiler/ports.py`, `retrieval/ports.py` → shims
- Extend smoke tests for `ExtractorPort`, `CompilerPort`, `Hit`, `RetrievalMode`, `RetrievalPort`

**Interfaces:**
- Produces: unchanged DTO/Protocol APIs via both import paths

- [ ] **Step 1: Move + shim**

- [ ] **Step 2: Run retrieval/compiler focused tests**

```bash
pytest tests/test_retrieval.py tests/test_compiler.py tests/test_fusion.py tests/test_reranker.py -v
```

- [ ] **Step 3: Commit**

```bash
git commit -m "refactor: move compiler and retrieval ports into hub"
```

---

### Task 4: Move evolution / verification / orchestrator ports

**Files:**
- Create: `akos/domain/ports/{evolution,verification,orchestrator}.py`
- Modify: legacy shims
- Extend smoke tests

- [ ] **Step 1: Move + shim**

- [ ] **Step 2:**

```bash
pytest tests/test_evolution_applier.py tests/test_verification_service.py tests/test_orchestrator.py -v
```

- [ ] **Step 3: Commit**

```bash
git commit -m "refactor: move evolution/verification/orchestrator ports into hub"
```

---

### Task 5: Move DomainPort + barrel export

**Files:**
- Create: `akos/domain/ports/domain.py` (body of `DomainPort` from `domains/base.py`)
- Modify: `domains/base.py` → re-export `DomainPort` (keep any non-port helpers if present)
- Modify: `akos/domain/ports/__init__.py` to export main Ports for convenience
- Note: `domains/base.py` currently imports `compiler.ports` / `ontology.ports` — after shims, either keep shim imports or point at hub (prefer hub inside new `domain.py` to avoid cycles: hub ports must not import `domains`)

**Cycle rule:** `akos.domain.ports.domain` may import other `akos.domain.ports.*` and `knowledge.models` (models still outside hub in Phase 1). It must **not** import `domains.*` packages.

- [ ] **Step 1: Move DomainPort carefully; fix imports to use hub + `knowledge.models` / `compiler.extraction_spec`**

- [ ] **Step 2:**

```bash
pytest tests/test_domains.py tests/test_kb_isolation.py tests/test_hybrid_extraction_api.py -v
```

- [ ] **Step 3: Commit**

```bash
git commit -m "refactor: move DomainPort into akos.domain.ports"
```

---

### Task 6: Full regression + docs touch

**Files:**
- Modify: `docs/superpowers/specs/2026-09-17-akos-hexagonal-restructure-design.md` — mark Phase 1 done
- Optional: README one-liner under architecture pointing at `akos.domain.ports`

- [ ] **Step 1: Full test suite**

```bash
pytest -q
```

- [ ] **Step 2: Update spec checklist Phase 1 = done**

- [ ] **Step 3: Commit**

```bash
git commit -m "docs: mark hexagonal Phase 1 port hub complete"
```

---

## Phase 1 done when

- [ ] Every former `*/ports.py` is a shim
- [ ] `from akos.domain.ports.X import Y` works for all moved symbols
- [ ] `Hub is Shim` identity holds (same object)
- [ ] Full pytest green
- [ ] No adapter/use-case files moved

## Next plan (not this document)

Phase 2: `akos/adapters/persistence|llm|retrieval` — see design spec §6.
