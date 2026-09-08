# Phase 2.1 Task 3 Report: DomainPort + 领域注册表

**Status:** DONE  
**Date:** 2026-09-08  
**Baseline:** 5336c55 (Task 1)  
**Commit:** feat: add DomainPort registry and ecommerce domain plugin

## TDD Execution

| Step | Action | Result |
|------|--------|--------|
| 1 | Write `tests/test_domain_port.py` | Done |
| 2 | Implement `domains/base.py`, `registry.py`, domain plugins | Done |
| 3 | Run `pytest tests/test_domain_port.py -v` | **9 passed** |
| 4 | Full suite `pytest -v` | **28 passed, 9 skipped** |
| 5 | Commit | feat: add DomainPort registry and ecommerce domain plugin |

## Files Created

- `domains/base.py` — `DomainPort` Protocol（ontology、extractor、aliases、format_claim、low_confidence_message）
- `domains/registry.py` — `DOMAIN_REGISTRY` + `load_domain(name)`
- `domains/ecommerce_cs/domain.py` — `EcommerceCsDomain` 调用 `seed.register_ecommerce_cs`
- `domains/ecommerce_cs/formatter.py` — 电商谓词可读化（排除/适用类目/运费承担方）
- `domains/generic/domain.py` — `GenericDomain` + `register_generic_ontology`
- `domains/corporate_culture/domain.py` — skeleton，复用 generic ontology
- `domains/loan_finance/domain.py` — skeleton，复用 generic ontology
- `tests/test_domain_port.py` — load_domain、format_claim、ontology 注册、未知域错误

## Unchanged (Task 5 scope)

- `infra/bootstrap.py` — 仍直接调用 `register_ecommerce_cs`
- `orchestrator/nodes.py` — 仍使用 `_ALIAS_CANDIDATES` 与 `_claim_to_text`

## API Example

```python
from domains.registry import load_domain
from ontology.registry import InMemoryOntology
from knowledge.models import Claim

domain = load_domain("ecommerce_cs")
ontology = InMemoryOntology()
domain.register_ontology(ontology)

claim = Claim(
    id="c1", family_id="f1", version=1,
    subject="七天无理由", predicate="排除", object="定制商品",
    subject_type="RefundRule", object_type="Category",
    confidence=0.9, status="active",
    valid_from=None, valid_to=None, source_ids=["s1"],
)
print(domain.format_claim(claim))  # 定制商品不适用七天无理由
print(domain.get_aliases())        # ['7天无理由', '七天无理由退货', ...]
```

## Registry

| domain_type | Class | Extractor | Ontology |
|-------------|-------|-----------|----------|
| `ecommerce_cs` | `EcommerceCsDomain` | `RuleExtractor` | ecommerce seed |
| `corporate_culture` | `CorporateCultureDomain` | `RuleExtractor` (stub) | generic |
| `loan_finance` | `LoanFinanceDomain` | `RuleExtractor` (stub) | generic |
| `generic` | `GenericDomain` | `RuleExtractor` (stub) | Concept 谓词 |

## Tests

```
pytest tests/test_domain_port.py -v → 9 passed
pytest -v → 28 passed, 9 skipped
```

## Next Task

Task 4: `PgGraph` / `PgEvidence` / `PgMemory`（kb 作用域）  
Task 5: `build_orchestrator_for_kb` — 接入 `load_domain` 并重构 `orchestrator/nodes.py`
