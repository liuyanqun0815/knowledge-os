# compiled-wiki Task 8 Report

**Status:** DONE  
**Commit:** (filled after commit)

## What changed

- `admin_api/routes_wiki.py`: `POST .../wiki/compile` (optional `source_id`) + `POST .../chunks/purge-stale` (kb-wide or `?source_id=`)
- `admin_api/schemas.py`: `WikiCompileResponse`, `PurgeStaleChunksResponse`
- `web/src/components/SourceChunksPanel.tsx`: default fetch `status=active`; summary drops stale count emphasis
- `README.md`: compile-layer path `{AKOS_DATA_ROOT}/kb/{kb_id}/wiki/` + compile/purge admin APIs
- `tests/test_admin_wiki_compile_api.py`: compile writes topic pages; purge deletes stale

## Verification

```text
pytest tests/test_admin_wiki_compile_api.py -q
3 passed

cd web && npx vitest run src/components/SourceChunksPanel.test.tsx
1 passed
```

## Notes

- Compile API always runs when called (manual override); reindexes `wiki_retrieval` when present
- Purge API ignores `AKOS_PURGE_STALE_CHUNKS` auto flag (one-shot / historical cleanup)
