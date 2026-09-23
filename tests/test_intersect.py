import pytest

from akos.adapters.llm.client import LlmConfigError
from akos.application.ingest.intersect import (
    extract_llm_claims_from_text,
    intersect_extracted,
    select_hybrid_candidates,
    union_extracted,
)
from akos.domain.ports.compiler import ExtractedClaim
from akos.application.ingest.rule_extractor import RuleExtractor
from akos.domains.ecommerce_cs.rules import ECOMMERCE_RULES
from akos.domains.ecommerce_cs.seed import register_ecommerce_cs
from infra.settings import Settings
from akos.adapters.ontology.memory import InMemoryOntology


def test_intersect_extracted_keeps_only_matching_triples():
    rule = ExtractedClaim(
        subject="七天无理由",
        predicate="运费承担方",
        object="买家",
        confidence=0.9,
        quote="七天无理由退货运费承担方为买家",
        start=0,
        end=15,
    )
    llm_match = ExtractedClaim(
        subject="七天无理由",
        predicate="运费承担方",
        object="买家",
        confidence=0.8,
        quote="买家承担",
        start=10,
        end=14,
    )
    llm_other = ExtractedClaim(
        subject="七天无理由",
        predicate="排除",
        object="定制商品",
        confidence=0.8,
        quote="定制商品不适用",
        start=0,
        end=8,
    )

    merged = intersect_extracted([rule], [llm_match, llm_other])

    assert len(merged) == 1
    assert merged[0].predicate == "运费承担方"
    assert merged[0].quote == rule.quote
    assert merged[0].confidence == 0.9


def test_union_extracted_keeps_both_channels_and_merges_overlap():
    rule = ExtractedClaim(
        subject="七天无理由",
        predicate="运费承担方",
        object="买家",
        confidence=0.9,
        quote="七天无理由退货运费承担方为买家",
        start=0,
        end=15,
    )
    llm_match = ExtractedClaim(
        subject="七天无理由",
        predicate="运费承担方",
        object="买家",
        confidence=0.8,
        quote="买家承担",
        start=10,
        end=14,
    )
    llm_only = ExtractedClaim(
        subject="七天无理由",
        predicate="排除",
        object="定制商品",
        confidence=0.85,
        quote="定制商品不适用",
        start=0,
        end=8,
    )

    merged = union_extracted([rule], [llm_match, llm_only])

    assert len(merged) == 2
    by_predicate = {claim.predicate: claim for claim in merged}
    assert by_predicate["运费承担方"].quote == rule.quote
    assert by_predicate["运费承担方"].confidence == 0.9
    assert by_predicate["排除"].object == "定制商品"


def test_select_hybrid_candidates_uses_union_when_both_enabled():
    onto = InMemoryOntology()
    register_ecommerce_cs(onto)
    text = "七天无理由退货运费承担方为买家。定制商品不适用七天无理由退货。"

    class MockLlm:
        is_configured = True

    class MockDomain:
        def llm_extraction_spec(self):
            from akos.application.ingest.extraction_spec import LlmExtractionSpec

            return LlmExtractionSpec(allowed_predicates=["运费承担方", "排除"], entity_types=["RefundRule"])

    llm_claims = [
        ExtractedClaim(
            subject="七天无理由",
            predicate="运费承担方",
            object="买家",
            confidence=0.85,
            quote="七天无理由退货运费承担方为买家",
            start=0,
            end=15,
        ),
        ExtractedClaim(
            subject="七天无理由",
            predicate="排除",
            object="平台",
            confidence=0.85,
            quote="定制商品不适用七天无理由退货",
            start=16,
            end=30,
        ),
    ]

    class MockLlmExtractor:
        def __init__(self, client, spec):
            pass

        def extract(
            self,
            chunk: str,
            *,
            document_anchor=None,
            section_title=None,
            section_summary=None,
        ):
            return llm_claims

    import akos.application.ingest.intersect as intersect_module

    original_extractor = intersect_module.DomainLlmExtractor
    intersect_module.DomainLlmExtractor = MockLlmExtractor
    try:
        settings = Settings(llm_api_key="test")
        candidates = select_hybrid_candidates(
            text,
            rule_extractor=RuleExtractor(ECOMMERCE_RULES),
            llm_client=MockLlm(),
            domain=MockDomain(),
            settings=settings,
            ontology=onto,
        )
    finally:
        intersect_module.DomainLlmExtractor = original_extractor

    predicates = {claim.predicate for claim in candidates}
    objects = {(claim.predicate, claim.object) for claim in candidates}
    assert "运费承担方" in predicates
    assert ("排除", "定制商品") in objects
    assert ("排除", "平台") in objects


def test_extract_llm_claims_from_text_passes_document_anchor(monkeypatch):
    import akos.application.ingest.intersect as intersect_module

    calls: list[str | None] = []
    resolve_calls: list[str | None] = []

    class FakeExtractor:
        def __init__(self, *args, **kwargs):
            pass

        def extract(self, text, *, document_anchor=None, section_title=None, section_summary=None):
            calls.append(document_anchor)
            return []

    monkeypatch.setattr(intersect_module, "DomainLlmExtractor", FakeExtractor)
    monkeypatch.setattr(
        intersect_module,
        "resolve_document_anchor",
        lambda text, title=None: resolve_calls.append(title) or "锚点产品",
    )

    class MockLlm:
        is_configured = True

    class MockDomain:
        def llm_extraction_spec(self):
            from akos.application.ingest.extraction_spec import LlmExtractionSpec

            return LlmExtractionSpec(allowed_predicates=["倡导"], entity_types=["Concept"])

    settings = Settings(chunk_max_chars=3000, llm_api_key="test")
    extract_llm_claims_from_text(
        "公司倡导诚信经营。",
        MockLlm(),
        MockDomain(),
        settings,
        title="产品说明书.md",
    )

    assert calls and calls[0] == "锚点产品"
    assert resolve_calls == ["产品说明书.md"]


def test_select_hybrid_candidates_raises_when_extract_llm_unconfigured():
    settings = Settings(llm_api_key="")
    with pytest.raises(LlmConfigError, match="入库 Claim 抽取"):
        select_hybrid_candidates(
            "七天无理由退货运费承担方为买家。",
            rule_extractor=RuleExtractor(ECOMMERCE_RULES),
            llm_client=type("L", (), {"is_configured": False})(),
            domain=type("D", (), {"llm_extraction_spec": lambda self: None})(),
            settings=settings,
        )
