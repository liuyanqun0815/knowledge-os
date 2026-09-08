# Task 7 Report: F3 Ask Page with Evidence and Trace

## Status

Completed on branch `feat/admin-web`.

## Implementation

- Added a knowledge-base-scoped ask form with question and optional `datetime-local` as-of input.
- Submitted questions through `askQuestion`, using the response `text` field and converting as-of values to ISO strings.
- Added expandable evidence cards with `span` summaries, full JSON details, and an empty fallback.
- Added an ordered Agent trace timeline with statuses, summaries, durations, expandable details, and an unavailable fallback.
- Cleared answers and invalidated pending requests when the selected knowledge base changes.
- Replaced the `/ask` placeholder with the functional page and added responsive result styling.

## TDD Evidence

- RED: component and page suites first failed because `EvidenceList`, `TraceTimeline`, and `AskPage` did not exist.
- RED: the router test failed against the placeholder, and the pending-answer test reproduced stale results after switching knowledge bases.
- GREEN: focused tests passed with 3 files and 12 tests.
- Full suite: `npm test` passed with 9 files and 26 tests.
- Production build: `npm run build` completed successfully.
- IDE diagnostics and `git diff --check`: no errors.

## Self-review

- Verified the page does not call the API without a selected knowledge base.
- Verified the request uses `knowledgeBaseId`, trimmed question text, and an optional ISO `asOf`.
- Verified inline `response.trace` is preferred and empty traces display `轨迹暂不可用`.
- Verified evidence and trace details remain collapsed until explicitly expanded.
- Verified stale asynchronous answers cannot repopulate results after a knowledge-base switch.
- Verified only Task 7 implementation, tests, styles, router, and this report are staged.

## Concerns

- ~~The backend currently exposes no admin trace-fetch endpoint, so responses without inline trace use the specified unavailable fallback.~~ Addressed: frontend now calls `GET /admin/knowledge-bases/{id}/traces/{request_id}` when inline trace is empty.
- Evidence is intentionally rendered from the generic `Record<string, unknown>` API contract; `span` is the only promoted summary field.

## Task 7 Review Fix: fetchTrace secondary path

**Date:** 2026-09-08

### Changes

- Added `fetchTrace(kbId, requestId)` in `web/src/api/ask.ts` — GET `/admin/knowledge-bases/${kbId}/traces/${requestId}` via `apiFetch`, returns `trace` array or `[]`.
- Updated `AskPage.handleSubmit`: after `askQuestion`, when `(response.trace ?? []).length === 0` and `response.request_id` is set, calls `fetchTrace`; on failure keeps empty steps and shows「轨迹暂不可用」.

### Test evidence

```text
cd web && npm test -- src/pages/AskPage.test.tsx src/api/ask.test.ts

 ✓ src/api/ask.test.ts (3 tests)
 ✓ src/pages/AskPage.test.tsx (8 tests)

 Test Files  2 passed (2)
      Tests  11 passed (11)
```

- `ask.test.ts`: `fetchTrace` GET path + empty payload fallback.
- `AskPage.test.tsx`: secondary fetch on empty trace + request_id; success renders steps; failure shows degradation.
