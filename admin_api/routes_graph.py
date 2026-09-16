from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from admin_api.graph_helpers import (
    build_snapshot,
    entity_name,
    filter_edges,
    list_predicates,
    search_entities,
    to_edge_response,
    to_entity_response,
)
from admin_api.routes_sources import _resolve_active_kb
from admin_api.schemas import GraphEntityResponse, GraphNeighborsResponse, GraphSnapshotResponse
from app.deps import build_orchestrator_for_request

router = APIRouter(prefix="/knowledge-bases", tags=["admin-graph"])


@router.get("/{kb_id}/graph/snapshot", response_model=GraphSnapshotResponse)
def graph_snapshot(
    kb_id: str,
    request: Request,
    entity_limit: int = Query(default=200, ge=1, le=1000),
    edge_limit: int = Query(default=500, ge=1, le=5000),
    active_only: bool = Query(default=True),
    _: None = Depends(_resolve_active_kb),
) -> GraphSnapshotResponse:
    orchestrator = build_orchestrator_for_request(kb_id, request)
    entities, edges, truncated, entity_total = build_snapshot(
        orchestrator.deps.graph,
        entity_limit=entity_limit,
        edge_limit=edge_limit,
        knowledge=orchestrator.deps.knowledge,
        active_only=active_only,
    )
    return GraphSnapshotResponse(
        entities=entities,
        edges=edges,
        truncated=truncated,
        entity_total=entity_total,
    )


@router.get("/{kb_id}/graph/entities", response_model=list[GraphEntityResponse])
def list_graph_entities(
    kb_id: str,
    request: Request,
    q: str | None = Query(default=None),
    predicate: str | None = Query(default=None),
    limit: int = Query(default=500, ge=1, le=2000),
    active_only: bool = Query(default=True),
    _: None = Depends(_resolve_active_kb),
) -> list[GraphEntityResponse]:
    orchestrator = build_orchestrator_for_request(kb_id, request)
    return search_entities(
        orchestrator.deps.graph,
        q=q,
        predicate=predicate,
        limit=limit,
        knowledge=orchestrator.deps.knowledge,
        active_only=active_only,
    )


@router.get("/{kb_id}/graph/predicates", response_model=list[str])
def list_graph_predicates(
    kb_id: str,
    request: Request,
    q: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    active_only: bool = Query(default=True),
    _: None = Depends(_resolve_active_kb),
) -> list[str]:
    orchestrator = build_orchestrator_for_request(kb_id, request)
    return list_predicates(
        orchestrator.deps.graph,
        q=q,
        limit=limit,
        knowledge=orchestrator.deps.knowledge,
        active_only=active_only,
    )


@router.get("/{kb_id}/graph/entities/{entity_id}/neighbors", response_model=GraphNeighborsResponse)
def graph_entity_neighbors(
    kb_id: str,
    entity_id: str,
    request: Request,
    predicates: list[str] | None = Query(default=None),
    depth: int = Query(default=1, ge=1, le=3),
    active_only: bool = Query(default=True),
    _: None = Depends(_resolve_active_kb),
) -> GraphNeighborsResponse:
    orchestrator = build_orchestrator_for_request(kb_id, request)
    graph = orchestrator.deps.graph
    if graph.get_entity(entity_id) is None:
        return GraphNeighborsResponse(entity_id=entity_id)

    raw_edges = list(graph.neighbors(entity_id, predicates=predicates, depth=depth))
    kept = filter_edges(
        graph,
        raw_edges,
        knowledge=orchestrator.deps.knowledge,
        active_only=active_only,
    )
    edges = [to_edge_response(graph, edge) for edge in kept]

    neighbor_ids: set[str] = set()
    for edge in edges:
        if edge.dst != entity_id:
            neighbor_ids.add(edge.dst)
        if edge.src != entity_id:
            neighbor_ids.add(edge.src)

    entities: list[GraphEntityResponse] = []
    for neighbor_id in sorted(neighbor_ids):
        props = graph.get_entity(neighbor_id)
        if props is None:
            entities.append(GraphEntityResponse(id=neighbor_id, type="Concept", name=entity_name(graph, neighbor_id)))
        else:
            entities.append(to_entity_response(neighbor_id, props))

    return GraphNeighborsResponse(entity_id=entity_id, entities=entities, edges=edges)
