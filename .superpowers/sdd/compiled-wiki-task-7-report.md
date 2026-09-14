# compiled-wiki Task 7 Report

**Status:** DONE  
**Commit:** `4a7f6c053e718fa1780265d9f26eedfa302e0a16`

## What changed

- `retrieval/fusion.py`: `fuse_hits` accepts optional `wiki_hits` + `wiki_weight` / `chunk_weight`; three-way weighted RRF; two-way callers keep legacy `chunk_weight = 1 - claim_weight`
- `orchestrator/nodes.py`: Ask retrieve searches `wiki_retrieval` when `wiki_compile`; fuses with settings weights; verify/synthesize pass `wiki_pages`
- `orchestrator/synthesis.py`: context + prompt include `## Wiki 主题页` and grounding rule (numbers/rules from Claim/原文; Wiki = structure only)
- `orchestrator/state.py` / `service.py`: `wiki_hits` / `wiki_pages` on Ask state
- `compiler/chunk_enrichment.py`: after compile, reindex wiki root via `deps.wiki_retrieval`
- Tests: `test_fuse_hits_prefers_strong_wiki_when_claim_chunk_weak`, `test_build_prompt_includes_wiki_section_and_grounding_rule`

## Verification

```text
pytest tests/test_fusion.py tests/test_synthesis.py tests/test_retrieval.py tests/test_wiki_retrieval.py tests/test_trace_utils.py tests/test_orchestrator.py -q
21 passed
```

## Notes

- Empty `wiki_hits` keeps two-way fuse + `route_fusion_weights`
- Link expand (P2) not enabled
