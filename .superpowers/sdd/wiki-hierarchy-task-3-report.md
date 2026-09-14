# Wiki Hierarchy Task 3 Report

**Commit:** (filled after commit) (`feat: use path-based wiki topic links without topic- prefix`)

## Done
- `wiki/links.py`: `topic_page_path(hub, leaf=None)` → `hub/_index` or `hub/leaf` (no `topic-` prefix)
- `topic_wikilink(hub, leaf=None, label=None, *, hierarchy_enabled=True)` path form by default
- `topic_page_name(name)` kept for legacy flat `topic-{name}` / `hierarchy_enabled=False`
- `compile.py` / `export.py` call flat wikilinks until Task 4 hierarchy compile

## Files
- `wiki/links.py`, `wiki/compile.py`, `wiki/export.py`, `tests/test_wiki_links.py`

## Verify
```bash
pytest tests/test_wiki_links.py tests/test_wiki_export.py tests/test_wiki_compile.py -q  # 16 passed
```

## TDD
- RED: ImportError (`topic_page_path` missing)
- GREEN: 8 link tests + existing export/compile flat assertions
