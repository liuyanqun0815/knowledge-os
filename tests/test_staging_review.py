from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from akos.interfaces.api.admin_api.claim_helpers import approve_staging_claim, reject_staging_claim
from knowledge.errors import DomainError
from akos.adapters.persistence.knowledge_memory import InMemoryKnowledge
from knowledge.models import Claim


def _claim(
    claim_id: str,
    *,
    family_id: str = "fam-1",
    object_value: str = "买家",
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
        valid_from=datetime.now(timezone.utc),
        valid_to=None,
        source_ids=["s1"],
    )


def test_approve_staging_supersedes_active_and_activates():
    knowledge = InMemoryKnowledge()
    knowledge.append_claim(_claim("c-old", object_value="买家", status="active", version=1))
    knowledge.append_claim(_claim("c-staging", object_value="平台", status="staging", version=2))
    indexed: list[str] = []
    removed: list[str] = []
    deps = SimpleNamespace(
        knowledge=knowledge,
        graph=SimpleNamespace(
            upsert_entity=lambda *args, **kwargs: None,
            upsert_relation=lambda *args, **kwargs: None,
        ),
        retrieval=SimpleNamespace(
            index_claim=lambda claim: indexed.append(claim.id),
            remove_claim=lambda claim_id: removed.append(claim_id),
        ),
    )

    active = approve_staging_claim(deps, "c-staging")

    assert active.status == "active"
    assert active.object == "平台"
    assert knowledge.get_claim("c-old").status == "superseded"
    assert knowledge.get_claim("c-staging").status == "superseded"
    assert removed == ["c-old"]
    assert indexed == [active.id]


def test_reject_staging_marks_superseded():
    knowledge = InMemoryKnowledge()
    knowledge.append_claim(_claim("c-old", object_value="买家", status="active", version=1))
    knowledge.append_claim(_claim("c-staging", object_value="平台", status="staging", version=2))
    deps = SimpleNamespace(knowledge=knowledge, graph=None, retrieval=None)

    reject_staging_claim(deps, "c-staging")

    assert knowledge.get_claim("c-staging").status == "superseded"
    assert knowledge.get_claim("c-old").status == "active"


def test_approve_staging_rejects_non_staging():
    knowledge = InMemoryKnowledge()
    knowledge.append_claim(_claim("c-active", status="active"))
    deps = SimpleNamespace(knowledge=knowledge, graph=None, retrieval=None)

    try:
        approve_staging_claim(deps, "c-active")
        raise AssertionError("expected DomainError")
    except DomainError as exc:
        assert "not_staging" in str(exc)
