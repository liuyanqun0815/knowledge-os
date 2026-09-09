# Phase 2.4 Task 5 Report — Adapter parity + CLI AnswerV2

**Baseline:** Phase 2.4 Task 4 (`f7d51de` — admin API claims/quarantine/debug)

**Commit:** `test: add graph adapter parity tests and CLI AnswerV2 fields`

## Summary

Added golden-set graph adapter parity tests comparing `InMemoryGraph`, `PgGraph`, and `Neo4jGraph` neighbor query results. Extended `akos ask` CLI output with AnswerV2 fields (`verification_status`, `competing_claim_ids`, `procedure_id`, conditional `as_of`).

## Files created

| File | Purpose |
|------|---------|
| `tests/test_adapter_parity.py` | Golden set (2 entities + 1 relation → neighbors); InMemory vs PgGraph parity; Neo4j skip unless `AKOS_GRAPH_BACKEND=neo4j` |

## Files modified

| File | Change |
|------|--------|
| `cli/main.py` | `ask` JSON output adds `verification_status`, `competing_claim_ids`, `procedure_id`; `as_of` only when set (ISO8601) |

## Golden set

Shared operations across adapters:

1. `upsert_entity("e_rule", "RefundRule", …)`
2. `upsert_entity("e_cat", "Category", …)`
3. `upsert_relation("e_rule", "适用类目", "e_cat", …)`
4. `neighbors("e_rule", predicates=["适用类目"], depth=1)` → one edge to `e_cat`

Edges normalized as sorted `(src, predicate, dst)` tuples for cross-adapter comparison.

## Test matrix

| Test | Condition | Result |
|------|-----------|--------|
| `test_inmemory_golden_set` | always | PASS |
| `test_pg_graph_parity_with_inmemory` | `AKOS_USE_PG=true` | SKIP (no PG in CI env) |
| `test_neo4j_graph_parity_with_inmemory` | `AKOS_GRAPH_BACKEND=neo4j` | SKIP (no Neo4j in CI env) |

## CLI example

```bash
akos ask "定制商品能否七天无理由退货？" --kb <kb_id>
```

Output now includes:

```json
{
  "text": "...",
  "claim_ids": ["..."],
  "evidence": [...],
  "confidence": 0.9,
  "retrieval_mode": "hybrid",
  "verification_status": "verified",
  "competing_claim_ids": [],
  "procedure_id": null
}
```

When temporal query resolves `as_of`:

```json
{
  "...": "...",
  "as_of": "2024-06-30T00:00:00+00:00"
}
```

## Verification

```bash
pytest tests/test_adapter_parity.py -v
# 1 passed, 2 skipped

pytest -v
# 97 passed, 22 skipped
```

## Next

- Task 6: Phase 2.4 E2E acceptance (already present as `tests/test_phase24_e2e.py`; README Phase 2.4 section pending separate commit)
