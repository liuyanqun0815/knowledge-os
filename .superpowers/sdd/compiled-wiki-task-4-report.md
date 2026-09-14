# compiled-wiki Task 4 Report

**Status:** DONE  
**Commit:** `c1004e319937368759e21fe3ce8fbe97d555a16c`

## What changed

- `wiki/links.py`: shared wikilink/filename helpers extracted from export
- `wiki/compile.py`: `compile_topics_for_source` template path → `topic-*.md` (摘要/Chunks/Claims/相关原文/相关主题), `index.md` topic section, `.meta/pages.json`
- `wiki/export.py`: reuses `wiki.links` (private aliases kept)
- `compiler/chunk_enrichment.py`: after enrich + topic rebuild, if `wiki_compile` and `data_root` → compile (segmentation WIP not committed)

## Verification

```text
pytest tests/test_wiki_compile.py tests/test_wiki_export.py tests/test_wiki_paths_meta.py -q
12 passed
```

## Notes

- Template only (LLM merge = Task 5)
- Two sources sharing a topic rewrite one `topic-*.md` with both `[[source-...]]` links
- Local `chunk_enrichment` segmentation WIP restored after commit with same compile hook
