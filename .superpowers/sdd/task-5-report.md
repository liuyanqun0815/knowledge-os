# Task 5 Report: Update AskPage / ask API tests

## Status

**PASS** — all required assertions updated for chat UI; no production UI changes needed.

## What changed

- `web/src/pages/AskPage.test.tsx`: rewrote failing assertions for chat UI
  - Empty KB → EmptyState
  - After ask: answer text + `sessionId: expect.any(String)` on `askQuestion`
  - Evidence hidden until expand retrieve/verify step
  - No `已核验` / `核验状态` / conflict badge
  - Confidence `90%`, retrieval mode `HYBRID`, duration from `duration_ms`
  - Second ask appends two user questions
  - `kbId` change clears messages
  - Button label remains `提问`
- `web/src/api/ask.test.ts`: added `session_id` body coverage when `sessionId` provided

## UI gaps

None. Task 4 already renders `EvidenceList` under expanded retrieve/verify, passes `sessionId`, and omits verification summary.

## Tests

```text
cd web && npm test -- src/pages/AskPage.test.tsx src/api/ask.test.ts src/components/AskExecutionCard.test.tsx
# 3 files, 16 passed
```

## Commit

`test: cover ask chat session memory and hide verification summary`

## Self-review

- [x] All 8 brief assertions covered
- [x] Old conflict / competing-claim / procedure assertions removed
- [x] Trace fallback uses Chinese label (`生成回答`) with `|answer` fallback
- [x] `ask.test.ts` sessionId coverage present
- [x] No unrelated production edits

## Concerns

- Retrieval mode assertion uses mock value `HYBRID` (uppercase); if backend returns `hybrid`, the summary still shows the raw string unless a future task uppercases it.

---

# Final Review Fix: wall-clock `duration_ms` + evidence UX

## Status

**PASS**

## What changed

- `knowledge/models.py`: `Answer.duration_ms: int | None = None`
- `orchestrator/service.py`: `ask()` measures with `time.perf_counter()`, sets via `dataclasses.replace` (also when `include_trace`)
- `app/routes.py`: `AskResponse.duration_ms` + serialize from answer
- `tests/test_ask_node_duration.py`: assert non-null wall-clock `duration_ms` on Answer (trace + non-trace)
- `EvidenceList`: prefer `span`, fallback to `quote`
- `AskExecutionCard`: attach evidence only under `verify` (avoid retrieve duplicate)

## Tests

```text
python -m pytest tests/test_ask_node_duration.py -q --tb=short
# 3 passed in 1.08s

cd web && npm test -- src/pages/AskPage.test.tsx src/components/AskExecutionCard.test.tsx src/components/EvidenceList.test.tsx
# 3 files, 15 passed
```

## Commit

`fix: expose ask wall-clock duration_ms on Answer and API`

## Concerns

- Wall-clock is measured in `LangGraphOrchestrator.ask()` only; node-level `duration_ms` remain separate step timings.
- If `state["answer"]` is somehow `None`, duration is not attached (defensive guard).
