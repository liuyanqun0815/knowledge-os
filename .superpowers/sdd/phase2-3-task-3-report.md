# Phase 2.3 Task 3 Report — ask verify + agents

**Baseline:** `ef7f1a8` (Task 1 — verification service + AnswerV2 fields)

**Commit:** `feat: integrate verification agent into ask LangGraph pipeline`

## Summary

Integrated Verification Agent into the ask LangGraph pipeline with thin `agents/` wrappers and a new `verify` node between `retrieve` and `explain`.

## Changes

### 1. `agents/` thin wrappers (~20 lines each, Port-only)

| Agent | File | Wraps |
|-------|------|-------|
| retriever_agent | `agents/retriever_agent/service.py` | `retrieval.search` + `route_mode` |
| verification_agent | `agents/verification_agent/service.py` | `VerificationService.verify_claims` |
| memory_agent | `agents/memory_agent/service.py` | `memory.recall` / `remember_episode` |
| compiler_agent | `agents/compiler_agent/service.py` | `compiler.ingest` |
| evolution_agent | `agents/evolution_agent/service.py` | `evolution.diff_sources` / `apply_diff` |
| research_agent | `agents/research_agent/service.py` | stub — returns `claim_ids` unchanged |

### 2. AskState extensions (`orchestrator/state.py`)

- `verification: VerificationResult | None`
- `trace: Annotated[list[dict], operator.add]` (LangGraph reducer for append)

### 3. ask_graph topology

```
recall → parse_time → normalize → route_mode → retrieve → verify → explain → answer → remember
```

- **verify_node:** resolves `claim_ids` from hits (as_of-aware), runs `VerificationService`, stores `verification`, appends trace entry
- **explain_node:** uses `verification.verified_claim_ids` (or all `claim_ids` when status is `partial`)
- **answer_node:** sets `Answer.verification_status`, `competing_claim_ids`, `confidence` from `verification.adjusted_confidence`

### 4. Bootstrap wiring

- `OrchestratorDeps.verification: VerificationService`
- Instantiated in `_build_orchestrator_deps_for_kb`

### 5. Node refactors

- `recall_node` / `remember_node` → `memory_agent`
- `route_mode_node` / `retrieve_node` → `retriever_agent`

## Tests

`tests/test_verify_ask.py`:

| Test | Result |
|------|--------|
| Normal ingest → ask returns `verification_status=verified` | PASS |
| Bad evidence quotes on all source claims → `unverified` | PASS |

```bash
python -m pytest tests/test_verify_ask.py -v
# 2 passed
```

## Files touched

- Create: `agents/**/service.py` (6 agents)
- Modify: `orchestrator/state.py`, `orchestrator/nodes.py`, `orchestrator/graphs/ask_graph.py`, `orchestrator/service.py`, `infra/bootstrap.py`, `pyproject.toml`
- Create: `tests/test_verify_ask.py`
- Modify: `tests/test_orchestrator_graph.py` (initial state includes `trace`)

## Next (Task 4)

- Collect full LangGraph node trace in `orchestrator/service.py`
- Expose `verification_status`, `competing_claim_ids`, `trace` in `POST /ask` response
