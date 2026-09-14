# compiled-wiki Task 6 Report

**Status:** DONE  
**Commit:** (filled after commit)

## What changed

- `retrieval/wiki_index.py`: `WikiPageRetrieval.index_wiki_root` / `search` — BM25 token overlap + char-hash cosine (same pattern as `ChunkRetrieval`); indexes `.meta/pages.json` when present, else `topic-*.md` / `entity-*.md`
- `retrieval/ports.py`: `Hit` gains optional `ref_id`, `title`, `path` (`hit_type="wiki"` = ref_type)
- `infra/bootstrap.py`: when `wiki_compile`, attach `wiki_retrieval` and warm from `{data_root}/kb/{kb_id}/wiki` if present
- `tests/test_wiki_retrieval.py`: index + search + top_k

## Verification

```text
pytest tests/test_wiki_retrieval.py tests/test_chunk_retrieval.py tests/test_retrieval.py -q
8 passed
```

## Notes

- Ask-path three-way fusion remains Task 7 (`fuse_hits` not yet consuming wiki hits)
- Reindex after compile: call `index_wiki_root` on touched wiki root (Task 7 / enrich hook)
