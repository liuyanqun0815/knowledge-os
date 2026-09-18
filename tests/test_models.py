# tests/test_models.py
from datetime import datetime, timezone

from akos.domain.errors import QuarantineError
from akos.domain.models.knowledge import Answer, Claim, Source, TextSpan


def test_claim_is_versioned_not_overwritten_shape():
    claim = Claim(
        id="c1",
        family_id="f1",
        version=1,
        subject="七天无理由",
        predicate="适用类目",
        object="非定制商品",
        subject_type="RefundRule",
        object_type="Category",
        confidence=0.91,
        status="active",
        valid_from=datetime.now(timezone.utc),
        valid_to=None,
        source_ids=["s1"],
    )
    assert claim.version == 1
    assert claim.status == "active"


def test_quarantine_error_carries_reason_and_raw():
    err = QuarantineError(reason="invalid_predicate", raw={"predicate": "乱写"})
    assert err.reason == "invalid_predicate"
    assert err.raw["predicate"] == "乱写"


def test_answer_and_span():
    span = TextSpan(source_id="s1", start=10, end=40, quote="定制商品不适用")
    answer = Answer(
        text="不能",
        claim_ids=["c1"],
        evidence=[{"source_id": "s1", "quote": span.quote, "weight": 0.95}],
        confidence=0.93,
        retrieval_mode="CLAIM",
    )
    assert answer.confidence == 0.93
    assert Source(
        id="s1",
        title="退换货政策v3",
        type="policy",
        uri="file://x",
        version="3",
        created_at=datetime.now(timezone.utc),
        status="ready",
    ).type == "policy"
