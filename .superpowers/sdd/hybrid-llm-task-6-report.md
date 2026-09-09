# Task 6 Report: Background Upload Enrichment

## Status

Implemented upload-time `BackgroundTasks` scheduling and lifespan recovery for interrupted LLM enrichment on
`feat/hybrid-llm-extraction`.

## Changes

- Upload and ZIP ingestion remain rule-only synchronously, then schedule `enrich_source` once per successful source.
- Sources with enabled and configured LLM extraction are marked `enriching` before task registration so a process
  restart can discover unfinished work.
- The application lifespan loads active PostgreSQL knowledge bases, scans cached orchestrators, and retries only
  sources whose status is `enriching`; one failed retry does not prevent application startup or other retries.
- `SourceResponse` now exposes optional `enrichment_status`, derived from the persisted source status.
- Added API tests proving synchronous upload does not call the LLM, manually scheduled enrichment quarantines an
  unknown ecommerce predicate, and lifespan recovery ignores non-enriching sources.

## TDD Evidence

1. RED: `python -m pytest tests/test_hybrid_extraction_api.py -v`
   - `3 failed` for missing background scheduling and lifespan recovery.
2. GREEN: the same focused test file passed: `3 passed`.
3. Adjacent regression:
   - `14 passed, 2 skipped` across hybrid extraction API, enrichment runner, ZIP upload, and admin knowledge-base API
     when explicitly run in in-memory mode.
4. Full in-memory regression:
   - `138 passed, 22 skipped, 1 warning`.
5. Formatting and diagnostics:
   - Black with line length 120 left all five Python files unchanged.
   - Cursor diagnostics showed no new code errors; only the environment-level unresolved FastAPI import warning.

## Concerns

- Lifespan retries run synchronously during startup, so configured LLM latency can delay readiness while interrupted
  sources are recovered.
- PostgreSQL integration tests remain skipped unless `AKOS_USE_PG=true` and the test database are configured.
- Running nominal in-memory tests without overriding `AKOS_USE_PG=false` can pick up a local `.env` PostgreSQL setting;
  the full verification explicitly forced in-memory mode.
- Black emitted the existing Python 3.13 versus Python 3.14 target-syntax warning.
