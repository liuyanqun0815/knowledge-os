from __future__ import annotations

from akos.application.ingest.service import _entity_id
from akos.adapters.persistence.graph_memory import InMemoryGraph
from akos.adapters.persistence.pg_graph import PgGraph
from infra.settings import Settings
from akos.domain.models.knowledge import Claim
from akos.application.topics.service import rebuild_topic_clusters
from akos.application.wiki.cleanup import purge_wiki_for_deleted_source


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
        purge_orphans = getattr(deps.graph, "purge_orphans", None)
        if callable(purge_orphans):
            purge_orphans()

    if cfg.wiki_compile:
        purge_wiki_for_deleted_source(
            kb_id=deps.knowledge_base_id,
            source_id=source_id,
            knowledge=deps.knowledge,
            data_root=cfg.data_root,
            settings=cfg,
            graph=getattr(deps, "graph", None),
            llm_client=getattr(deps, "llm_client", None),
            wiki_retrieval=getattr(deps, "wiki_retrieval", None),
        )
