# compiled-wiki Task 2 Report

**Status:** DONE  
**Commit:** `bb959a9f29922cd8d740dbcf53723032f39ed301`

## What changed

- `knowledge/ports.py`: `purge_stale_chunks(source_id) -> int`
- `knowledge/memory_repo.py`: purge stale by `source_id`; `list_chunks` scans by source+status
- `infra/pg_repos.py`: delete stale `source_chunks` + matching `embeddings` (`ref_type='chunk'`)
- `compiler/chunk_service.py`: after `save_chunks`, purge when `settings.purge_stale_chunks`
- Segmentation call site purge left in local WIP `chunk_enrichment.py` (not staged; segmentation not on HEAD)

## Verification

```text
pytest tests/test_purge_stale_chunks.py -q
3 passed
```

## Notes

- Gate is at call site (`index_source_chunks`), not inside `save_chunks`
- `AKOS_PURGE_STALE_CHUNKS=false` retains stale rows after reindex
