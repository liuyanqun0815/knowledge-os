from __future__ import annotations

import uuid
from datetime import datetime, timezone

from akos.application.ingest.service import _entity_id
from akos.domain.errors import DomainError
from akos.domain.models.knowledge import Claim
from akos.domain.ports.knowledge import KnowledgePort


def _contains(haystack: str, needle: str) -> bool:
    return needle.casefold() in haystack.casefold()


def list_filtered_claims(
    knowledge: KnowledgePort,
    status: str | None = None,
    subject: str | None = None,
    predicate: str | None = None,
    object: str | None = None,
) -> list[Claim]:
    if status:
        claims = knowledge.get_claims_by_status(status)
    else:
        claims = []
        for claim_status in ("active", "staging", "quarantined", "superseded"):
            claims.extend(knowledge.get_claims_by_status(claim_status))

    subject_q = (subject or "").strip()
    predicate_q = (predicate or "").strip()
    object_q = (object or "").strip()
    if subject_q:
        claims = [claim for claim in claims if _contains(claim.subject, subject_q)]
    if predicate_q:
        claims = [claim for claim in claims if _contains(claim.predicate, predicate_q)]
    if object_q:
        claims = [claim for claim in claims if _contains(claim.object, object_q)]
    return claims


def index_approved_claim(deps, claim: Claim) -> None:
    subject_entity = _entity_id(claim.subject, claim.subject_type)
    object_entity = _entity_id(claim.object, claim.object_type)
    deps.graph.upsert_entity(subject_entity, claim.subject_type, {"name": claim.subject})
    deps.graph.upsert_entity(object_entity, claim.object_type, {"name": claim.object})
    deps.graph.upsert_relation(subject_entity, claim.predicate, object_entity, {})
    deps.retrieval.index_claim(claim)


def approve_staging_claim(deps, claim_id: str) -> Claim:
    """Human-approve a staging claim: supersede active peers, activate, reindex."""
    knowledge: KnowledgePort = deps.knowledge
    staging = knowledge.get_claim(claim_id)
    if staging is None:
        raise DomainError(f"claim_not_found: {claim_id}")
    if staging.status != "staging":
        raise DomainError(f"not_staging: {claim_id}")

    now = datetime.now(timezone.utc)
    history = knowledge.get_claim_history(staging.family_id)
    retrieval = getattr(deps, "retrieval", None)
    for peer in history:
        if peer.id == staging.id:
            continue
        if peer.status == "active":
            knowledge.mark_superseded(peer.id, valid_to=now)
            if retrieval is not None and hasattr(retrieval, "remove_claim"):
                retrieval.remove_claim(peer.id)

    knowledge.mark_superseded(staging.id, valid_to=now)
    active = Claim(
        id=str(uuid.uuid4()),
        family_id=staging.family_id,
        version=max((item.version for item in history), default=0) + 1,
        subject=staging.subject,
        predicate=staging.predicate,
        object=staging.object,
        subject_type=staging.subject_type,
        object_type=staging.object_type,
        confidence=staging.confidence,
        status="active",
        valid_from=now,
        valid_to=None,
        source_ids=list(staging.source_ids),
    )
    knowledge.append_claim(active)
    if getattr(deps, "graph", None) is not None and retrieval is not None:
        index_approved_claim(deps, active)
    return active


def reject_staging_claim(deps, claim_id: str) -> Claim:
    """Human-reject a staging claim without touching existing active peers."""
    knowledge: KnowledgePort = deps.knowledge
    staging = knowledge.get_claim(claim_id)
    if staging is None:
        raise DomainError(f"claim_not_found: {claim_id}")
    if staging.status != "staging":
        raise DomainError(f"not_staging: {claim_id}")
    knowledge.mark_superseded(staging.id, valid_to=datetime.now(timezone.utc))
    rejected = knowledge.get_claim(claim_id)
    assert rejected is not None
    return rejected
