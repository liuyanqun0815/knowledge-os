"""文档删除后的旁路数据清理：检索索引、图谱边、Wiki、主题簇。"""

from __future__ import annotations

from akos.application.ingest.service import _entity_id
from akos.domain.ports.graph import GraphPort
from infra.settings import Settings
from akos.domain.models.knowledge import Claim
from akos.application.topics.service import rebuild_topic_clusters
from akos.application.wiki.cleanup import purge_wiki_for_deleted_source


def sole_source_claims(knowledge, source_id: str) -> list[Claim]:
    return [claim for claim in knowledge.get_claims_for_source(source_id) if len(claim.source_ids) == 1]


def _active_spo_still_exists(knowledge, claim: Claim) -> bool:
    return any(
        other.subject == claim.subject
        and other.predicate == claim.predicate
        and other.object == claim.object
        for other in knowledge.get_claims_by_status("active")
    )


def _resolve_graph_for_purge(deps, settings: Settings) -> GraphPort:
    """删除旁路清理始终打到真实图存储；KB 关闭图谱时 deps.graph 可能是 NoOp。"""
    from akos.adapters.graph.noop import NoOpGraph

    graph = deps.graph
    if not isinstance(graph, NoOpGraph):
        return graph

    kb_id = deps.knowledge_base_id
    backend = settings.graph_backend.lower()
    if backend == "neo4j":
        from akos.adapters.graph.neo4j import Neo4jGraph

        return Neo4jGraph(
            uri=settings.neo4j_uri,
            user=settings.neo4j_user,
            password=settings.neo4j_password,
            knowledge_base_id=kb_id,
        )
    if backend == "postgres" and settings.use_pg:
        from infra.db import get_engine
        from akos.adapters.persistence.pg_graph import PgGraph

        return PgGraph(get_engine(settings), kb_id)
    return graph


def _active_chunk_ids(knowledge) -> set[str]:
    ids: set[str] = set()
    for source in knowledge.list_sources():
        for chunk in knowledge.list_chunks(source.id, status="active"):
            ids.add(chunk.id)
    return ids


def _purge_sole_claim_graph(graph, knowledge, sole_claims: list[Claim]) -> None:
    """删除独有 Claim 对应的图边；若实体不再参与任何边则删实体。"""
    delete_relation = getattr(graph, "delete_relation", None)
    delete_entity = getattr(graph, "delete_entity", None)
    list_relations = getattr(graph, "list_relations", None)
    if not callable(delete_relation):
        return

    touched: set[str] = set()
    for claim in sole_claims:
        if _active_spo_still_exists(knowledge, claim):
            continue
        src = _entity_id(claim.subject, claim.subject_type)
        dst = _entity_id(claim.object, claim.object_type)
        delete_relation(src, claim.predicate, dst)
        touched.add(src)
        touched.add(dst)

    if not touched or not callable(delete_entity):
        return

    remaining_ids: set[str] = set()
    if callable(list_relations):
        for edge in list_relations():
            remaining_ids.add(edge.src)
            remaining_ids.add(edge.dst)
    for entity_id in touched:
        if entity_id not in remaining_ids:
            delete_entity(entity_id)


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

    graph = _resolve_graph_for_purge(deps, cfg)
    ephemeral = graph is not deps.graph
    close_graph = getattr(graph, "close", None)
    try:
        _purge_sole_claim_graph(graph, deps.knowledge, sole_claims)

        if cfg.topic_cluster:
            rebuild_topic_clusters(deps.knowledge, graph, deps.knowledge_base_id, cfg)

        purge_orphans = getattr(graph, "purge_orphans", None)
        if callable(purge_orphans):
            purge_orphans(valid_chunk_ids=_active_chunk_ids(deps.knowledge))
    finally:
        if ephemeral and callable(close_graph):
            close_graph()

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
