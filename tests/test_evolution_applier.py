from datetime import datetime, timezone

from akos.application.evolution.applier import KnowledgeApplier
from akos.application.evolution.differ import KnowledgeDiffer
from akos.application.evolution.family import family_key
from akos.domain.ports.evolution import KnowledgeDiff
from akos.adapters.persistence.knowledge_memory import InMemoryKnowledge
from knowledge.models import Claim, Source


def _source(sid: str, version: str = "3") -> Source:
    return Source(
        id=sid,
        title=f"policy-{sid}",
        type="policy",
        uri=f"file://{sid}",
        version=version,
        created_at=datetime.now(timezone.utc),
        status="ready",
    )


def _claim(
    claim_id: str,
    source_id: str,
    *,
    family_id: str,
    object_value: str,
    status: str = "active",
    version: int = 1,
    valid_from: datetime | None = None,
) -> Claim:
    return Claim(
        id=claim_id,
        family_id=family_id,
        version=version,
        subject="七天无理由",
        predicate="运费承担方",
        object=object_value,
        subject_type="RefundRule",
        object_type="Concept",
        confidence=0.9,
        status=status,
        valid_from=valid_from or datetime(2024, 1, 1, tzinfo=timezone.utc),
        valid_to=None,
        source_ids=[source_id],
    )


def test_apply_diff_supersedes_old_and_activates_staging():
    repo = InMemoryKnowledge()
    old_id, new_id = "s-v3", "s-v4"
    repo.save_source(_source(old_id, "3"))
    repo.save_source(_source(new_id, "4"))
    fid = family_key("七天无理由", "运费承担方", "Concept")
    repo.append_claim(_claim("c-old", old_id, family_id=fid, object_value="买家", status="active"))
    repo.append_claim(_claim("c-staging", new_id, family_id=fid, object_value="平台", status="staging"))

    diff = KnowledgeDiffer(repo).diff_sources(old_id, new_id)
    report = KnowledgeApplier(repo).apply_diff(diff)

    old = repo.get_claim("c-old")
    assert old is not None
    assert old.status == "superseded"
    assert old.valid_to is not None

    active = repo.get_active_claims("七天无理由", "运费承担方")
    assert len(active) == 1
    assert active[0].object == "平台"
    assert active[0].version == 2
    assert active[0].status == "active"
    assert active[0].id in report.claims_activated
    assert "c-old" in report.claims_superseded
    assert len(report.events_created) >= 1


def test_apply_diff_activates_added_claims():
    repo = InMemoryKnowledge()
    old_id, new_id = "s-old", "s-new"
    repo.save_source(_source(old_id))
    repo.save_source(_source(new_id))
    fid_new = family_key("七天无理由", "退货时限_天", "Concept")
    staging = Claim(
        id="c-added-staging",
        family_id=fid_new,
        version=1,
        subject="七天无理由",
        predicate="退货时限_天",
        object="7",
        subject_type="RefundRule",
        object_type="Concept",
        confidence=0.9,
        status="staging",
        valid_from=datetime(2024, 6, 1, tzinfo=timezone.utc),
        valid_to=None,
        source_ids=[new_id],
    )
    repo.append_claim(staging)

    diff = KnowledgeDiff(
        source_old_id=old_id,
        source_new_id=new_id,
        claims_added=["c-added-staging"],
        claims_superseded=[],
        entities_changed=[],
        events=[],
    )
    report = KnowledgeApplier(repo).apply_diff(diff)

    active = repo.get_active_claims("七天无理由", "退货时限_天")
    assert len(active) == 1
    assert active[0].object == "7"
    assert active[0].status == "active"
    assert active[0].id in report.claims_activated


def test_as_of_returns_claim_valid_at_query_time():
    repo = InMemoryKnowledge()
    fid = family_key("七天无理由", "运费承担方", "Concept")
    t0 = datetime(2024, 1, 1, tzinfo=timezone.utc)
    t1 = datetime(2024, 6, 1, tzinfo=timezone.utc)
    t2 = datetime(2024, 12, 1, tzinfo=timezone.utc)

    c1 = _claim("c-v1", "s1", family_id=fid, object_value="买家", version=1, valid_from=t0)
    c1.valid_to = t1
    c1.status = "superseded"
    c2 = _claim("c-v2", "s2", family_id=fid, object_value="平台", version=2, valid_from=t1)
    repo.append_claim(c1)
    repo.append_claim(c2)

    at_mid = repo.as_of(datetime(2024, 3, 1, tzinfo=timezone.utc), fid)
    assert at_mid is not None
    assert at_mid.object == "买家"

    at_late = repo.as_of(t2, fid)
    assert at_late is not None
    assert at_late.object == "平台"

    before_start = repo.as_of(datetime(2023, 12, 1, tzinfo=timezone.utc), fid)
    assert before_start is None


def test_get_claims_for_source_and_by_status():
    repo = InMemoryKnowledge()
    fid = family_key("七天无理由", "运费承担方", "Concept")
    repo.append_claim(_claim("c1", "s1", family_id=fid, object_value="买家", status="active"))
    repo.append_claim(_claim("c2", "s2", family_id=fid, object_value="平台", status="staging"))

    by_source = repo.get_claims_for_source("s1")
    assert [c.id for c in by_source] == ["c1"]

    staging = repo.get_claims_by_status("staging")
    assert [c.id for c in staging] == ["c2"]
