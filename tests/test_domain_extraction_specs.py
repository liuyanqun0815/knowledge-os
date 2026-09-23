from __future__ import annotations

import pytest

from akos.domains.corporate_culture.domain import CorporateCultureDomain
from akos.domains.ecommerce_cs.domain import EcommerceCsDomain
from akos.domains.ecommerce_cs.seed import ENTITY_SEEDS, PREDICATES as EC_PREDICATES
from akos.domains.generic.domain import GenericDomain
from akos.domains.loan_finance.domain import LoanFinanceDomain
from akos.domains.loan_finance.seed import ENTITY_SEEDS as LOAN_ENTITY_SEEDS
from akos.domains.loan_finance.seed import PREDICATES as LOAN_PREDICATES
from akos.domains.registry import load_domain

EC_SEED_PREDICATES = sorted({predicate for _, predicate, _ in EC_PREDICATES})
EC_SEED_ENTITY_TYPES = sorted(
    set(ENTITY_SEEDS.values()) | {subject for subject, _, _ in EC_PREDICATES} | {obj for _, _, obj in EC_PREDICATES}
)
LOAN_SEED_PREDICATES = sorted({predicate for _, predicate, _ in LOAN_PREDICATES})


def test_ecommerce_spec_matches_ontology_seed() -> None:
    spec = EcommerceCsDomain().llm_extraction_spec()

    assert sorted(spec.allowed_predicates) == EC_SEED_PREDICATES
    assert sorted(spec.entity_types) == EC_SEED_ENTITY_TYPES


def test_corporate_spec_has_culture_predicates() -> None:
    spec = CorporateCultureDomain().llm_extraction_spec()

    assert spec.allowed_predicates == ["倡导", "禁止", "适用于"]
    assert set(spec.entity_types) == {"Value", "Behavior", "Policy", "Department", "Concept"}


def test_generic_spec_has_wide_predicates() -> None:
    spec = GenericDomain().llm_extraction_spec()

    assert set(spec.allowed_predicates) == {"规定", "适用于", "禁止", "要求", "相关", "定义", "属于"}
    assert spec.entity_types == ["Concept", "Policy"]


def test_loan_finance_spec_has_product_subject_hints() -> None:
    spec = LoanFinanceDomain().llm_extraction_spec()

    assert sorted(spec.allowed_predicates) == LOAN_SEED_PREDICATES
    assert "Product" in spec.entity_types
    assert set(LOAN_ENTITY_SEEDS.values()).issubset(set(spec.entity_types))
    assert spec.few_shot_hints is not None
    assert len(spec.few_shot_hints) >= 2
    assert any("正例" in hint for hint in spec.few_shot_hints)
    assert any("反例" in hint for hint in spec.few_shot_hints)


@pytest.mark.parametrize("domain_type", ["ecommerce_cs", "corporate_culture", "generic", "loan_finance"])
def test_all_domains_have_nonempty_extraction_spec(domain_type: str) -> None:
    spec = load_domain(domain_type).llm_extraction_spec()

    assert len(spec.allowed_predicates) > 0
    assert len(spec.entity_types) > 0
