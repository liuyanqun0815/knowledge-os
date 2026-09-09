# Phase 2.3 Task 4 Report — LangGraph trace + POST /ask AnswerV2

**Baseline:** `544ca32` (Task 3 — verification agent in ask pipeline)

**Commit:** `feat: expose LangGraph trace and AnswerV2 in ask API`

## Summary

Exposed LangGraph node trace and AnswerV2 fields (`verification_status`, `competing_claim_ids`, `procedure_id`) through `orchestrator.ask()` and `POST /ask`.

## Changes

### 1. `orchestrator/service.py`

- Added `AskResult` dataclass (`answer`, `trace`)
- `ask(..., include_trace=False)` returns `Answer` by default; when `include_trace=True`, returns `AskResult` with trace collected from `AskState.trace`

### 2. `orchestrator/nodes.py`

- `retrieve_node` appends trace entry: `{"node": "retrieve", "hit_count", "retrieval_mode"}`
- `verify_node` (Task 3) already appends: `{"node": "verify", "claim_ids", "verification_status"}`

### 3. `app/routes.py`

- `AskRequest.include_trace: bool = False`
- `AskResponse` extended: `verification_status`, `competing_claim_ids`, `procedure_id`
- `POST /ask` accepts `?include_trace=true` query param or body `include_trace`; populates `trace` when requested

### 4. Tests

- Updated `FakeOrchestrator` in `tests/test_ask_kb_and_trace.py` for new signature and AnswerV2 fields
- Created `tests/test_ask_trace.py`:
  - orchestrator `include_trace=True` → trace contains `retrieve`, `verify`
  - API response includes `verification_status` and trace
  - query param `?include_trace=true` works

```bash
python -m pytest tests/test_ask_trace.py tests/test_ask_kb_and_trace.py -v
# 7 passed
```

## Files touched

- Modify: `orchestrator/service.py`, `orchestrator/nodes.py`, `app/routes.py`, `tests/test_ask_kb_and_trace.py`
- Create: `tests/test_ask_trace.py`

## Next (Task 5)

- E2E acceptance: unverified / conflict / trace (`tests/test_verification_e2e.py`)
- README Phase 2.3 验收章节
