# Wiki Hierarchy Task 5 Report

**Commit:** `9627aaa` (`feat: index nested wiki pages and align export paths`)

## Done
- `retrieval/wiki_index.py`: fallback index uses `rglob("*.md")`, skips `.meta`, stores relative paths with `/`; nested hub/leaf pages indexable without `topic-` prefix
- `wiki/export.py`: when `settings.wiki_hierarchy`, assign ecommerce seeds and write topics to `hub/leaf.md` (snippets → target path); index wikilinks use path form
- Flat export (no settings / hierarchy off) unchanged

## Files
- `retrieval/wiki_index.py`, `wiki/export.py`, `tests/test_wiki_retrieval.py`, `tests/test_wiki_export.py`

## Verify
```bash
pytest tests/test_wiki_retrieval.py tests/test_wiki_export.py -q  # 11 passed
```

## TDD
- RED: nested `客服话术/沟通规范.md` → empty hits; export hub path missing
- GREEN: nested searchable; hierarchy export writes hub paths
