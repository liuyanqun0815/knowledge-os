from __future__ import annotations

import pytest

from akos.domains.registry import load_domain
from akos.domain.errors import DomainError
from akos.domain.models.knowledge import Claim
from akos.adapters.ontology.memory import InMemoryOntology


def _sample_claim(**overrides: object) -> Claim:
    defaults = {
        "id": "c1",
        "family_id": "f1",
        "version": 1,
        "subject": "七天无理由",
        "predicate": "适用类目",
        "object": "非定制商品",
        "subject_type": "RefundRule",
        "object_type": "Category",
        "confidence": 0.9,
        "status": "active",
        "valid_from": None,
        "valid_to": None,
        "source_ids": ["s1"],
    }
    defaults.update(overrides)
    return Claim(**defaults)


def test_load_ecommerce_cs_domain():
    domain = load_domain("ecommerce_cs")
    assert domain.name == "ecommerce_cs"
    aliases = domain.get_aliases()
    assert "七天无理由" in aliases
    assert "7天无理由" in aliases


def test_ecommerce_format_claim_exclude():
    domain = load_domain("ecommerce_cs")
    claim = _sample_claim(predicate="排除", object="定制商品")
    assert domain.format_claim(claim) == "定制商品不适用七天无理由"


def test_ecommerce_format_claim_category():
    domain = load_domain("ecommerce_cs")
    claim = _sample_claim(predicate="适用类目", object="非定制商品")
    assert domain.format_claim(claim) == "七天无理由适用类目为非定制商品"


def test_ecommerce_format_claim_shipping():
    domain = load_domain("ecommerce_cs")
    claim = _sample_claim(predicate="运费承担方", object="卖家")
    assert domain.format_claim(claim) == "七天无理由运费承担方为卖家"


def test_ecommerce_register_ontology():
    domain = load_domain("ecommerce_cs")
    ontology = InMemoryOntology()
    domain.register_ontology(ontology)
    assert ontology.normalize_term("7天无理由") == "七天无理由"
    assert ontology.resolve_entity_type("七天无理由") == "RefundRule"


def test_load_unknown_domain_raises():
    with pytest.raises(DomainError, match="unknown domain_type"):
        load_domain("unknown_domain")


@pytest.mark.parametrize("domain_type", ["generic", "corporate_culture", "loan_finance"])
def test_load_skeleton_domains(domain_type: str):
    domain = load_domain(domain_type)
    assert domain.name == domain_type
    assert domain.low_confidence_message()
    assert domain.get_extractor() is not None
