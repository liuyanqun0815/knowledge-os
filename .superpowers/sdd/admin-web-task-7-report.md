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

- The backend currently exposes no admin trace-fetch endpoint, so responses without inline trace use the specified unavailable fallback.
- Evidence is intentionally rendered from the generic `Record<string, unknown>` API contract; `span` is the only promoted summary field.
