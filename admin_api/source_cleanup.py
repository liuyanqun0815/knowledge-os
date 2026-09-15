from __future__ import annotations

from compiler.service import _entity_id
from graph.memory_repo import InMemoryGraph
from infra.pg_graph import PgGraph
from infra.settings import Settings
from knowledge.models import Claim
from knowledge.topic_service import rebuild_topic_clusters


def sole_source_claims(knowledge, source_id: str) -> list[Claim]:
    return [claim for claim in knowledge.get_claims_for_source(source_id) if len(claim.source_ids) == 1]


def _purge_memory_claim_relations(graph: InMemoryGraph, knowledge, sole_claims: list[Claim]) -> None:
    active_claims = knowledge.get_claims_by_status("active")
    for claim in sole_claims:
        if any(
            other.subject == claim.subject and other.predicate == claim.predicate and other.object == claim.object
            for other in active_claims
        ):
            continue
        src = _entity_id(claim.subject, claim.subject_type)
        dst = _entity_id(claim.object, claim.object_type)
        graph.relations = [
            edge
            for edge in graph.relations
            if not (edge.src == src and edge.predicate == claim.predicate and edge.dst == dst)
        ]


def purge_source_side_effects(
    deps,
    source_id: str,
    *,
    sole_claims: list[Claim],
    settings: Settings | None = None,
) -> None:
    cfg = settings or Settings()
    deps.chunk_retrieval.remove_source(source_id)
    remove_claim = getattr(deps.retrieval, "remove_claim", None)
    if remove_claim is not None:
        for claim in sole_claims:
            remove_claim(claim.id)

    if isinstance(deps.graph, InMemoryGraph):
        _purge_memory_claim_relations(deps.graph, deps.knowledge, sole_claims)

    if cfg.topic_cluster:
        rebuild_topic_clusters(deps.knowledge, deps.graph, deps.knowledge_base_id, cfg)

    if isinstance(deps.graph, PgGraph):
        deps.graph.purge_orphans()
