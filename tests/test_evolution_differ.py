from datetime import datetime, timezone

import pytest

from akos.application.evolution.differ import KnowledgeDiffer
from akos.application.evolution.family import family_key
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
        valid_from=datetime(2024, 1, 1, tzinfo=timezone.utc),
        valid_to=None,
        source_ids=[source_id],
    )


def test_family_key_matches_compiler():
    from akos.application.ingest.service import _family_id

    subject, predicate, object_type = "七天无理由", "运费承担方", "Concept"
    assert family_key(subject, predicate, object_type) == _family_id(subject, predicate, object_type)


def test_diff_sources_supersede_when_same_family_object_changes():
    repo = InMemoryKnowledge()
    old_id, new_id = "s-v3", "s-v4"
    repo.save_source(_source(old_id, "3"))
    repo.save_source(_source(new_id, "4"))
    fid = family_key("七天无理由", "运费承担方", "Concept")
    repo.append_claim(_claim("c-old", old_id, family_id=fid, object_value="买家", status="active"))
    repo.append_claim(_claim("c-new", new_id, family_id=fid, object_value="平台", status="staging"))

    diff = KnowledgeDiffer(repo).diff_sources(old_id, new_id)

    assert diff.source_old_id == old_id
    assert diff.source_new_id == new_id
    assert diff.claims_added == []
    assert diff.claims_superseded == [("c-old", "c-new")]


def test_diff_sources_adds_new_families():
    repo = InMemoryKnowledge()
    old_id, new_id = "s-old", "s-new"
    repo.save_source(_source(old_id))
    repo.save_source(_source(new_id))
    fid_existing = family_key("七天无理由", "运费承担方", "Concept")
    fid_new = family_key("七天无理由", "退货时限_天", "Concept")
    repo.append_claim(_claim("c-old", old_id, family_id=fid_existing, object_value="买家", status="active"))
    repo.append_claim(_claim("c-new-changed", new_id, family_id=fid_existing, object_value="平台", status="staging"))
    repo.append_claim(
        Claim(
            id="c-new-added",
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
    )

    diff = KnowledgeDiffer(repo).diff_sources(old_id, new_id)

    assert diff.claims_superseded == [("c-old", "c-new-changed")]
    assert diff.claims_added == ["c-new-added"]


def test_diff_sources_ignores_unchanged_families():
    repo = InMemoryKnowledge()
    old_id, new_id = "s-a", "s-b"
    repo.save_source(_source(old_id))
    repo.save_source(_source(new_id))
    fid = family_key("七天无理由", "运费承担方", "Concept")
    repo.append_claim(_claim("c-old", old_id, family_id=fid, object_value="买家", status="active"))
    repo.append_claim(_claim("c-new", new_id, family_id=fid, object_value="买家", status="staging"))

    diff = KnowledgeDiffer(repo).diff_sources(old_id, new_id)

    assert diff.claims_superseded == []
    assert diff.claims_added == []
