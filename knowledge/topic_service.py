from __future__ import annotations

import hashlib

from akos.application.ingest.service import _entity_id
from akos.domain.ports.graph import GraphPort
from infra.settings import Settings
from knowledge.models import Claim, SourceChunk, TopicCluster
from akos.domain.ports.knowledge import KnowledgePort
from knowledge.topic_cluster import build_topic_clusters


def topic_entity_id(kb_id: str, name: str) -> str:
    digest = hashlib.sha256(f"{kb_id}|{name}".encode()).hexdigest()[:16]
    return f"topic:{digest}"


def _find_entity_by_name(graph: GraphPort, name: str) -> str | None:
    for entity_id, props in graph.list_entities():
        if props.get("type") in {"Topic", "Chunk"}:
            continue
        if props.get("name") == name:
            return entity_id
    return None


def _ensure_named_entity(graph: GraphPort, name: str) -> str:
    existing = _find_entity_by_name(graph, name)
    if existing is not None:
        return existing
    entity_id = _entity_id(name, "Concept")
    graph.upsert_entity(entity_id, "Concept", {"name": name})
    return entity_id


def _mark_kb_topics_stale(graph: GraphPort, kb_id: str) -> None:
    for entity_id, props in list(graph.list_entities()):
        if props.get("type") != "Topic":
            continue
        if props.get("kb_id") != kb_id:
            continue
        updated = dict(props)
        updated["status"] = "stale"
        entity_type = updated.pop("type", "Topic")
        graph.upsert_entity(entity_id, entity_type, updated)


def sync_graph_topics(
    graph: GraphPort,
    clusters: list[TopicCluster],
    *,
    claims: list[Claim],
    chunks: list[SourceChunk],
    graph_chunks: bool = True,
) -> None:
    claims_by_id = {claim.id: claim for claim in claims}
    chunks_by_id = {chunk.id: chunk for chunk in chunks}

    for cluster in clusters:
        topic_id = topic_entity_id(cluster.knowledge_base_id, cluster.name)
        graph.upsert_entity(
            topic_id,
            "Topic",
            {
                "name": cluster.name,
                "kb_id": cluster.knowledge_base_id,
                "status": "active",
            },
        )

        linked_names: set[str] = set()
        for claim_id in cluster.claim_ids:
            claim = claims_by_id.get(claim_id)
            if claim is None:
                continue
            for name in (claim.subject, claim.object):
                if not name or name in linked_names:
                    continue
                linked_names.add(name)
                entity_id = _ensure_named_entity(graph, name)
                graph.upsert_relation(topic_id, "涵盖", entity_id, {})

        if not graph_chunks:
            continue
        for chunk_id in cluster.chunk_ids:
            chunk = chunks_by_id.get(chunk_id)
            if chunk is None:
                continue
            chunk_entity_id = f"chunk:{chunk.id}"
            title = chunk.title if chunk.title else str(chunk.chunk_index)
            graph.upsert_entity(chunk_entity_id, "Chunk", {"title": title})
            graph.upsert_relation(topic_id, "包含段落", chunk_entity_id, {})


def rebuild_topic_clusters(
    knowledge: KnowledgePort,
    graph: GraphPort,
    knowledge_base_id: str,
    settings: Settings,
) -> list[TopicCluster]:
    if not settings.topic_cluster:
        return []

    chunks: list[SourceChunk] = []
    for source in knowledge.list_sources():
        chunks.extend(knowledge.list_chunks(source.id, status="active"))
    claims = knowledge.get_claims_by_status("active")

    clusters = build_topic_clusters(
        knowledge_base_id=knowledge_base_id,
        chunks=chunks,
        claims=claims,
        min_chunks=settings.topic_min_chunks,
    )

    knowledge.mark_topic_clusters_stale()
    knowledge.save_topic_clusters(clusters)
    _mark_kb_topics_stale(graph, knowledge_base_id)
    sync_graph_topics(
        graph,
        clusters,
        claims=claims,
        chunks=chunks,
        graph_chunks=settings.topic_graph_chunks,
    )
    return clusters
