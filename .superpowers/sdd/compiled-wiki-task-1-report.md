# compiled-wiki Task 1 Report

**Status:** DONE  
**Commit:** (filled after commit)

## What changed

- `infra/settings.py`: added `purge_stale_chunks`, `wiki_compile`, `wiki_compile_llm`, retrieval weights, `wiki_link_expand` with plan defaults
- `.env.example` / `README.md`: documented new env vars
- `tests/test_wiki_compile_settings.py`: asserts defaults with `_env_file=None` + delenv

## Verification

```text
pytest tests/test_wiki_compile_settings.py -q
1 passed
```

## Defaults

| Field | Default |
|-------|---------|
| purge_stale_chunks | True |
| wiki_compile | True |
| wiki_compile_llm | True |
| retrieval_claim_weight | 1.0 |
| retrieval_wiki_weight | 0.9 |
| retrieval_chunk_weight | 0.8 |
| wiki_link_expand | False |
