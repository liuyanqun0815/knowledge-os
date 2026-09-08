from datetime import datetime, timezone

from knowledge.memory_repo import InMemoryKnowledge
from knowledge.models import Claim, Source


def _source(sid: str = "s1") -> Source:
    return Source(
        id=sid,
        title="policy",
        type="policy",
        uri="file://p",
        version="3",
        created_at=datetime.now(timezone.utc),
        status="ready",
    )


def test_append_claim_keeps_history_and_active_filter():
    repo = InMemoryKnowledge()
    repo.save_source(_source())
    c1 = Claim(
        id="c1",
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
        source_ids=["s1"],
    )
    repo.append_claim(c1)
    c2 = Claim(
        id="c2",
        family_id="f1",
        version=2,
        subject="七天无理由",
        predicate="运费承担方",
        object="平台",
        subject_type="RefundRule",
        object_type="Concept",
        confidence=0.95,
        status="active",
        valid_from=datetime.now(timezone.utc),
        valid_to=None,
        source_ids=["s1"],
    )
    # 模拟 supersede：先改旧再追加新（memory 层只存储，不自动 supersede）
    c1.status = "superseded"
    repo.append_claim(c1)
    repo.append_claim(c2)
    active = repo.get_active_claims("七天无理由", "运费承担方")
    assert len(active) == 1
    assert active[0].object == "平台"
    hist = repo.get_claim_history("f1")
    assert len(hist) >= 2
