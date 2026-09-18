from datetime import datetime, timezone

from akos.adapters.persistence.knowledge_memory import InMemoryKnowledge
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


def test_delete_source_updates_claim_references():
    repo = InMemoryKnowledge()
    repo.save_source(_source("s1"))
    repo.save_source_text("s1", "source text")
    only_source = Claim(
        id="c1",
        family_id="f1",
        version=1,
        subject="退款",
        predicate="期限",
        object="七天",
        subject_type="Policy",
        object_type="Duration",
        confidence=0.9,
        status="active",
        valid_from=datetime.now(timezone.utc),
        valid_to=None,
        source_ids=["s1"],
    )
    shared = Claim(
        id="c2",
        family_id="f2",
        version=1,
        subject="退款",
        predicate="凭证",
        object="订单",
        subject_type="Policy",
        object_type="Document",
        confidence=0.9,
        status="active",
        valid_from=datetime.now(timezone.utc),
        valid_to=None,
        source_ids=["s1", "s2"],
    )
    repo.append_claim(only_source)
    repo.append_claim(shared)

    repo.delete_source("s1")

    assert repo.get_source("s1") is None
    assert repo.get_source_text("s1") is None
    assert repo.get_claim("c1") is None
    assert shared.source_ids == ["s2"]


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
