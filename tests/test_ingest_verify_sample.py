from datetime import datetime, timezone

from domains.registry import load_domain
from knowledge.models import Claim, Source, TextSpan
from akos.application.ask.nodes import verify_sample_node


def test_ecommerce_high_risk_predicates():
    domain = load_domain("ecommerce_cs")
    predicates = domain.high_risk_predicates()
    assert "运费承担方" in predicates
    assert "退货时限_天" in predicates


def test_generic_high_risk_predicates_empty():
    domain = load_domain("generic")
    assert domain.high_risk_predicates() == []


def test_verify_sample_quarantines_high_risk_bad_span(build_orchestrator_deps):
    deps = build_orchestrator_deps()
    knowledge = deps.knowledge
    evidence = deps.evidence

    source = Source(
        id="s-bad-span",
        title="policy",
        type="policy",
        uri="file://p",
        version="1",
        created_at=datetime.now(timezone.utc),
        status="ready",
    )
    knowledge.save_source(source)
    knowledge.save_source_text("s-bad-span", "七天无理由退货运费承担方为买家。")

    claim = Claim(
        id="c-bad",
        family_id="f1",
        version=1,
        subject="七天无理由",
        predicate="运费承担方",
        object="买家",
        subject_type="RefundRule",
        object_type="Concept",
        confidence=0.9,
        status="active",
        valid_from=datetime.now(timezone.utc),
        valid_to=None,
        source_ids=["s-bad-span"],
    )
    knowledge.append_claim(claim)
    evidence.bind("c-bad", "s-bad-span", TextSpan("s-bad-span", 0, 5, "完全不存在的引用"), 0.9)
    deps.retrieval.index_claim(claim)

    quarantine_before = len(knowledge.list_quarantine())

    result = verify_sample_node({"source_id": "s-bad-span", "error": None}, deps)

    assert len(knowledge.list_quarantine()) == quarantine_before + 1
    assert result["verify_report"]["quarantined"] == 1
    assert result["verify_report"]["failed_claim_ids"] == ["c-bad"]

    quarantined_claim = knowledge.get_claim("c-bad")
    assert quarantined_claim is not None
    assert quarantined_claim.status == "quarantined"


def test_verify_sample_passes_valid_high_risk_span(build_orchestrator_deps):
    deps = build_orchestrator_deps()
    knowledge = deps.knowledge
    evidence = deps.evidence

    source = Source(
        id="s-good-span",
        title="policy",
        type="policy",
        uri="file://p",
        version="1",
        created_at=datetime.now(timezone.utc),
        status="ready",
    )
    knowledge.save_source(source)
    source_text = "七天无理由退货运费承担方为买家。"
    knowledge.save_source_text("s-good-span", source_text)

    claim = Claim(
        id="c-good",
        family_id="f2",
        version=1,
        subject="七天无理由",
        predicate="运费承担方",
        object="买家",
        subject_type="RefundRule",
        object_type="Concept",
        confidence=0.9,
        status="active",
        valid_from=datetime.now(timezone.utc),
        valid_to=None,
        source_ids=["s-good-span"],
    )
    knowledge.append_claim(claim)
    evidence.bind(
        "c-good",
        "s-good-span",
        TextSpan("s-good-span", 0, len(source_text), "七天无理由退货运费承担方为买家"),
        0.9,
    )

    quarantine_before = len(knowledge.list_quarantine())

    result = verify_sample_node({"source_id": "s-good-span", "error": None}, deps)

    assert len(knowledge.list_quarantine()) == quarantine_before
    assert result["verify_report"]["quarantined"] == 0
    assert result["verify_report"]["passed"] == 1
    assert knowledge.get_claim("c-good").status == "active"
