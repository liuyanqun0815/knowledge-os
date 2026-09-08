# Phase 2.1 Task 10 Report: Phase 1 e2e compatibility + full regression

**Status:** DONE  
**Date:** 2026-09-08  
**Baseline:** c8e52dc (Task 8 — CLI `--kb`)  
**Prior:** 7e82d40 (Task 9 — LLM stub + corporate skeleton)  
**Commit:** test: adapt phase-1 e2e to knowledge base scoped orchestrator

## TDD Execution

| Step | Action | Result |
|------|--------|--------|
| 1 | e2e uses `seeded_kb_id` + `build_orchestrator_for_kb` | Done (Task 6; verified Task 10) |
| 2 | `conftest.py` seeds PG kb `test-ecommerce` / InMemory `default` | Done |
| 3 | Full suite `pytest -v` | **35 passed, 18 skipped** (InMemory) |
| 4 | README Phase 2.1 acceptance commands | Done |
| 5 | Commit | test: adapt phase-1 e2e to knowledge base scoped orchestrator |

## e2e Adaptation

Phase 1 e2e previously used `build_default_orchestrator()`. Phase 2.1 scopes all data by `knowledge_base_id`:

```python
# tests/test_e2e_sample.py
def test_mvp_success_criterion(seeded_kb_id):
    orch = build_orchestrator_for_kb(seeded_kb_id)
    report = orch.ingest("samples/refund_policy_v3.md", "policy")
    assert report.claims_created > 0
    answer = orch.ask("定制商品能否七天无理由退货？")
    assert answer.claim_ids
    assert any("quote" in e for e in answer.evidence)
    assert 0 < answer.confidence <= 1
```

```python
# tests/conftest.py — session fixture
TEST_KB_NAME = "test-ecommerce"

@pytest.fixture(scope="session")
def seeded_kb_id(request):
    if not pg_enabled():
        return "default"  # InMemory synthetic kb
    pg_kb_repo = request.getfixturevalue("pg_kb_repo")
    kb = pg_kb_repo.create(name=TEST_KB_NAME, domain_type="ecommerce_cs", description="ci")
    return kb.id
```

| Mode | `seeded_kb_id` | Domain | Persistence |
|------|----------------|--------|-------------|
| InMemory (`AKOS_USE_PG=false`) | `"default"` | `ecommerce_cs` via settings | per-process |
| PostgreSQL (`AKOS_USE_PG=true`) | uuid of `test-ecommerce` kb | `ecommerce_cs` | cross-process |

## Files Modified

| File | Change |
|------|--------|
| `tests/test_e2e_sample.py` | `build_orchestrator_for_kb(seeded_kb_id)` + docstring |
| `tests/conftest.py` | `seeded_kb_id` fixture, `TEST_KB_NAME`, PG schema bootstrap |
| `README.md` | Phase 2.1 acceptance commands + spec §5.5 checklist |

## Acceptance Commands (README)

```bash
pytest -v
pytest -v tests/test_e2e_sample.py
AKOS_USE_PG=true pytest -v tests/test_pg_knowledge.py tests/test_kb_isolation.py tests/test_admin_kb_api.py tests/test_e2e_sample.py
```

## Test Results

```
pytest -v
# 35 passed, 18 skipped (InMemory default)

pytest -v tests/test_e2e_sample.py
# 1 passed
```

PG-only tests (`test_kb_isolation`, `test_knowledge_base`, `test_cli_kb_persistence`, etc.) skip when `AKOS_USE_PG=false`.

## Spec §5.5 Coverage (Task 10 item)

- [x] 一期 e2e 测试通过（测试库 `test-ecommerce` / InMemory `default`）

## Next

Phase 2.2 plan: evolution/, as_of, Time Query.
