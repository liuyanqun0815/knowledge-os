from datetime import datetime, timezone

from akos.adapters.persistence.evidence_memory import InMemoryEvidence
from akos.adapters.persistence.knowledge_memory import InMemoryKnowledge
from knowledge.models import Claim, Source, TextSpan
from verification.service import VerificationService


def _source(sid: str = "s1") -> Source:
    return Source(
        id=sid,
        title="policy",
        type="policy",
        uri="file://p",
        version="1",
        created_at=datetime.now(timezone.utc),
        status="ready",
    )


def _claim(
    claim_id: str,
    family_id: str = "f1",
    subject: str = "七天无理由",
    predicate: str = "运费承担方",
    object_value: str = "买家",
    status: str = "active",
) -> Claim:
    return Claim(
        id=claim_id,
        family_id=family_id,
        version=1,
        subject=subject,
        predicate=predicate,
        object=object_value,
        subject_type="RefundRule",
        object_type="Concept",
        confidence=0.9,
        status=status,
        valid_from=datetime.now(timezone.utc),
        valid_to=None,
        source_ids=["s1"],
    )


def test_span_match_passes():
    knowledge = InMemoryKnowledge()
    evidence = InMemoryEvidence()
    knowledge.save_source(_source())
    knowledge.save_source_text("s1", "定制商品不适用七天无理由退货。")
    knowledge.append_claim(_claim("c1"))
    evidence.bind("c1", "s1", TextSpan("s1", 0, 7, "定制商品不适用"), 0.95)

    result = VerificationService().verify_claims(knowledge, evidence, ["c1"])

    assert result.verification_status == "verified"
    assert result.verified_claim_ids == ["c1"]
    assert result.unverified_claim_ids == []
    assert result.competing_claim_ids == []
    assert result.adjusted_confidence == 0.95


def test_span_mismatch_unverified_and_confidence_halved():
    knowledge = InMemoryKnowledge()
    evidence = InMemoryEvidence()
    knowledge.save_source(_source())
    knowledge.save_source_text("s1", "定制商品不适用七天无理由退货。")
    knowledge.append_claim(_claim("c1"))
    evidence.bind("c1", "s1", TextSpan("s1", 0, 7, "完全不存在的引用"), 0.8)

    result = VerificationService().verify_claims(knowledge, evidence, ["c1"])

    assert result.verification_status == "unverified"
    assert result.verified_claim_ids == []
    assert result.unverified_claim_ids == ["c1"]
    assert result.adjusted_confidence == 0.4


def test_competing_active_claims_in_same_family_conflict():
    knowledge = InMemoryKnowledge()
    evidence = InMemoryEvidence()
    knowledge.save_source(_source())
    knowledge.save_source_text("s1", "买家承担退货运费。平台承担换货运费。")
    knowledge.append_claim(_claim("c1", object_value="买家"))
    knowledge.append_claim(_claim("c2", object_value="平台"))
    evidence.bind("c1", "s1", TextSpan("s1", 0, 8, "买家承担退货运费"), 0.9)
    evidence.bind("c2", "s1", TextSpan("s1", 9, 17, "平台承担换货运费"), 0.9)

    result = VerificationService().verify_claims(knowledge, evidence, ["c1", "c2"])

    assert result.verification_status == "conflict"
    assert set(result.competing_claim_ids) == {"c1", "c2"}
    assert result.verified_claim_ids == ["c1", "c2"]
    assert result.unverified_claim_ids == []
