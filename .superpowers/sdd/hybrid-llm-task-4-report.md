# Task 4 Report: KnowledgeCompiler.apply_extracted_claims

## Status

Implemented `KnowledgeCompiler.apply_extracted_claims` on `feat/hybrid-llm-extraction`.

## Changes

- Added confidence quarantine with reason `low_confidence`.
- Added source quote validation with reason `span_missing`; evidence offsets are resolved against the full source text.
- Added ontology validation quarantine with reason `invalid_predicate`.
- Reused `compiler.service._family_id` for history lookup and claim creation.
- Added exact family/object deduplication, controlled by `existing_skip`.
- Added active-family conflict handling: a different object is written as `staging`.
- Added append, graph, evidence, and active-only retrieval indexing behavior.
- Added eight focused tests in `tests/test_compiler_apply_extracted.py`.

## TDD Evidence

1. RED: `python -m pytest tests/test_compiler_apply_extracted.py -v`
   - 8 failed with the expected missing-method `AttributeError`.
2. GREEN: same command after implementation.
   - 8 passed.
3. Compiler regression:
   - `python -m pytest tests/test_compiler.py tests/test_compiler_staging.py tests/test_compiler_apply_extracted.py -v`
   - 15 passed.
4. Full regression with the in-memory backend:
   - `$env:AKOS_USE_PG='false'; Remove-Item Env:AKOS_EXTRACT_LLM -ErrorAction SilentlyContinue; python -m pytest`
   - 129 passed, 22 skipped, 1 warning.
5. Formatting and lint:
   - Black with line length 120 left both changed Python files unchanged.
   - Cursor diagnostics reported no errors.

## Concerns

- Running the full suite directly inherits `.env` with `AKOS_USE_PG=true`; without a seeded PostgreSQL database this produced 36 unrelated failures. The in-memory full-suite run passed.
- Black emitted an environment warning because Python 3.13 checked a project configured for Python 3.14 syntax; no files required reformatting.
