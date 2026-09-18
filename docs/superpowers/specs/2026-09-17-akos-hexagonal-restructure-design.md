# AKOS Hexagonal Package Restructure (方案 C)

**Date:** 2026-09-17  
**Status:** Approved direction (defaults: `akos.` prefix, phased, start with Port consolidation)  
**Baseline:** `09c062c` on `main`

## 1. Problem

Root-level packages are flat (`compiler`, `wiki`, `orchestrator`, `admin_api`, `infra`, …). Ports already exist but are scattered (`*/ports.py`), so dependency direction is hard to see and adapters mix with use-case code.

## 2. Goals

- Enforce **hexagonal dependency direction**: interfaces → application → domain ports; adapters implement ports.
- Keep **behavior identical** during migration (re-export shims until a final cleanup PR).
- Make the tree readable for newcomers without requiring a full rewrite in one PR.

## 3. Non-goals (this program)

- Rewriting LangGraph logic or changing Ask/Ingest semantics
- Merging `web/` into Python packages
- Introducing new runtime frameworks

## 4. Target layout

```text
akos/
  domain/
    models/           # Claim, Source, SourceChunk, Hit, Answer, … (gradual)
    ports/            # ALL Protocols (KnowledgePort, GraphPort, …)
  application/
    ingest/           # compiler use cases, ingest graph façade
    ask/              # ask graph, synthesis, verification orchestration
    wiki/             # compile / export / layout / source_plan
    evolution/        # differ / applier façade
  adapters/
    persistence/      # InMemory* + Pg*
    llm/
    retrieval/        # hybrid, chunk, wiki_index, embedder, reranker
    files/
    graph/            # neo4j adapter
  domains/            # DomainPort plugins (ecommerce_cs, loan_finance, …)
  interfaces/
    api/              # FastAPI app + admin_api
    cli/
  bootstrap.py        # composition root only
web/                  # unchanged (repo root)
docs/ deploy/ tests/  # stay at root; tests import via public paths
```

### Dependency rule

| Layer | May import |
|-------|------------|
| `domain` | stdlib + typing only (no FastAPI/SQLAlchemy/LLM) |
| `application` | `akos.domain` only (ports + models) |
| `adapters` | `akos.domain.ports` (+ infra libs) |
| `interfaces` | `akos.application`, `akos.bootstrap` |
| `bootstrap` | adapters + application wiring |

## 5. Mapping (current → target)

| Current | Target (eventual) |
|---------|-------------------|
| `knowledge/ports.py`, `evidence/ports.py`, … | `akos/domain/ports/*.py` |
| `knowledge/models.py`, `retrieval/ports.Hit`, … | `akos/domain/models/` (later phase) |
| `knowledge/memory_repo.py`, `infra/pg_repos.py`, … | `akos/adapters/persistence/` |
| `infra/llm.py` | `akos/adapters/llm/` |
| `retrieval/*` | `akos/adapters/retrieval/` |
| `compiler/*`, ingest nodes | `akos/application/ingest/` |
| ask graph + synthesis | `akos/application/ask/` |
| `wiki/*` | `akos/application/wiki/` |
| `app/`, `admin_api/` | `akos/interfaces/api/` |
| `cli/` | `akos/interfaces/cli/` |
| `domains/` | `akos/domains/` |
| `infra/bootstrap.py` | `akos/bootstrap.py` |

## 6. Phases

| Phase | Name | Deliverable | Risk | Status |
|-------|------|-------------|------|--------|
| **1** | Port hub + shims | Move Protocols under `akos.domain.ports`; old `*.ports` re-export | Low | **DONE 2026-09-17** |
| **2** | Adapters home | Move persistence/LLM/retrieval adapters; update bootstrap | Medium | **DONE 2026-09-18** |
| **3** | Application extract | Move use-case modules; thin LangGraph nodes | High | **DONE 2026-09-18** |
| **4** | Interfaces | Move API/CLI; update entrypoints / Docker | Medium | |
| **5** | Cleanup | Remove shims; fix `pyproject` includes; README | Low | |

**Gate for every phase:** full `pytest` green + smoke ask/ingest on local PG if available.

## 7. Compatibility policy

During phases 1–4:

```python
# e.g. knowledge/ports.py
from akos.domain.ports.knowledge import KnowledgePort  # noqa: F401
```

External/scripts may keep old imports until Phase 5.

## 8. Defaults locked by approval

- Package prefix: **`akos.`**
- Pace: **phased**; implement **Phase 1 first**
- Feature freeze: **preferred** during each phase PR; not a hard lock unless requested

## 9. Open follow-ups (not Phase 1)

- Whether `Hit` stays in retrieval or moves to `domain.models`
- Whether `DomainPort` lives under `akos.domain.ports` or `akos.domains`
- Splitting oversized `orchestrator/nodes.py` while extracting ask use cases
