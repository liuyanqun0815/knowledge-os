from __future__ import annotations

from compiler.service import _entity_id
from knowledge.models import Claim
from knowledge.ports import KnowledgePort


def list_filtered_claims(
    knowledge: KnowledgePort,
    status: str | None = None,
    subject: str | None = None,
) -> list[Claim]:
    if status:
        claims = knowledge.get_claims_by_status(status)
    else:
        claims = []
        for claim_status in ("active", "staging", "quarantined", "superseded"):
            claims.extend(knowledge.get_claims_by_status(claim_status))
    if subject:
        claims = [claim for claim in claims if claim.subject == subject]
    return claims


def index_approved_claim(deps, claim: Claim) -> None:
    subject_entity = _entity_id(claim.subject, claim.subject_type)
    object_entity = _entity_id(claim.object, claim.object_type)
    deps.graph.upsert_entity(subject_entity, claim.subject_type, {"name": claim.subject})
    deps.graph.upsert_entity(object_entity, claim.object_type, {"name": claim.object})
    deps.graph.upsert_relation(subject_entity, claim.predicate, object_entity, {})
    deps.retrieval.index_claim(claim)
