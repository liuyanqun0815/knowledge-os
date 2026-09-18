from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from akos.interfaces.api.admin_api.routes_sources import _resolve_active_kb
from akos.interfaces.api.admin_api.schemas import TopicRebuildResponse
from akos.interfaces.api.deps import build_orchestrator_for_request
from akos.application.topics.service import rebuild_topic_clusters, topic_entity_id

router = APIRouter(prefix="/knowledge-bases", tags=["admin-topics"])


@router.post("/{kb_id}/topics/rebuild", response_model=TopicRebuildResponse)
def rebuild_knowledge_base_topics(
    kb_id: str,
    request: Request,
    _: None = Depends(_resolve_active_kb),
) -> TopicRebuildResponse:
    orchestrator = build_orchestrator_for_request(kb_id, request)
    knowledge = orchestrator.deps.knowledge
    graph = orchestrator.deps.graph
    settings = request.app.state.settings

    previous_ids = {cluster.id for cluster in knowledge.list_topic_clusters(status="active")}
    clusters = rebuild_topic_clusters(knowledge, graph, kb_id, settings)
    new_ids = {cluster.id for cluster in clusters}

    topics_created = len(new_ids - previous_ids)
    topics_updated = len(new_ids & previous_ids)
    topics_stale = len(previous_ids - new_ids)

    edges = 0
    for cluster in clusters:
        topic_id = topic_entity_id(kb_id, cluster.name)
        edges += len(graph.neighbors(topic_id))

    return TopicRebuildResponse(
        topics_created=topics_created,
        topics_updated=topics_updated,
        topics_stale=topics_stale,
        edges=edges,
    )
