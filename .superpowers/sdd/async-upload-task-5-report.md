# Task 5 Report: Frontend accept UX + polling

## Status
DONE

## Changes
- `web/src/api/types.ts`: widened `compile_status`; added `accepted_async` / `ingest_summary` on `SourceUploadResponse`
- `web/src/components/SourceFileBrowser.tsx`: STATUS_LABELS for pending/running/enriching/ready/succeeded_partial
- `web/src/pages/SourcesPage.tsx`: async accept banner, clear upload spinner immediately, poll `listSources` every 2s up to ~180s while busy
- `web/src/pages/SourcesPage.test.tsx`: Vitest for banner `/后台编译中/` + polling; fixed upload call arity assertion

## Tests
```
npm test -- --run src/pages/SourcesPage.test.tsx
```
PASS — 7/7

## Commit
`feat: poll sources after async upload accept`

## Notes / Concerns
- `accepted_async !== false` treats missing field as async (per brief); legacy sync mocks without the flag also show accept banner and start polling
- Poll uses `listSources(kbId)` without search query (per brief), so active search filter is not applied during background poll
- Poll loop has no abort on unmount / kb switch; may setState after leave page until deadline or idle
- `SourceFileBrowser.tsx` commit also included pre-existing dirty UI changes (SourceDetailPanel / tree meta layout) already present on the working tree when Task 5 started

## Review fix (post d20562b)

### Fixes
1. **SourceFileBrowser.tsx**: restored to `0498671` baseline (`SourceClaimsPanel`, original layout/CSS classes), then re-applied only STATUS_LABELS widening (`pending`/`running`/`enriching`/`ready`/`succeeded`/`succeeded_partial`/`failed`). Removed unrelated SourceDetailPanel swap + tree-meta/layout refactors from Task 5 commit.
2. **AskResponse `duration_ms`**: removed duplicate field in `web/src/api/types.ts`; kept single `duration_ms?: number | null`.

### Kept (OK for branch)
- SourcesPage async accept banner + polling
- docs accept extensions (pdf/docx/doc)

### Re-test
```
npm test -- --run src/pages/SourcesPage.test.tsx
```
```
 ✓ src/pages/SourcesPage.test.tsx (7 tests) 2341ms
   ✓ sources page > lists source filenames and compile statuses 363ms
   ✓ sources page > uploads the selected file and refreshes the list 463ms
   ✓ sources page > accepts a dropped file and reports upload failures 351ms
   ✓ sources page > uploads a selected folder with browser relative paths 455ms
   ✓ sources page > shows async accept banner and polls until compile finishes 648ms

 Test Files  1 passed (1)
      Tests  7 passed (7)
```
PASS — 7/7
