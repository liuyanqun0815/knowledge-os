from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from akos.interfaces.api.admin_api.graph_helpers import (
    build_snapshot,
    filter_edges,
    list_predicates,
    search_entities,
    to_edge_response,
    to_entity_response,
)
from akos.interfaces.api.admin_api.routes_sources import _resolve_active_kb
from akos.interfaces.api.admin_api.schemas import (
    GraphEntityResponse,
    GraphNeighborsResponse,
    GraphRetrieveHitResponse,
    GraphRetrieveRequest,
    GraphRetrieveResponse,
    GraphSnapshotResponse,
)
from akos.interfaces.api.deps import build_orchestrator_for_request

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
    entities_map = dict(graph.list_entities())
    kept = filter_edges(
        graph,
        raw_edges,
        knowledge=orchestrator.deps.knowledge,
        active_only=active_only,
        entities=entities_map,
    )
    edges = [to_edge_response(graph, edge, entities_map) for edge in kept]

    neighbor_ids: set[str] = set()
    for edge in edges:
        if edge.dst != entity_id:
            neighbor_ids.add(edge.dst)
        if edge.src != entity_id:
            neighbor_ids.add(edge.src)

    entities: list[GraphEntityResponse] = []
    for neighbor_id in sorted(neighbor_ids):
        props = entities_map.get(neighbor_id)
        if props is None:
            entities.append(GraphEntityResponse(id=neighbor_id, type="Concept", name=neighbor_id))
        else:
            entities.append(to_entity_response(neighbor_id, props))

    return GraphNeighborsResponse(entity_id=entity_id, entities=entities, edges=edges)


@router.post("/{kb_id}/graph/retrieve", response_model=GraphRetrieveResponse)
def graph_retrieve(
    kb_id: str,
    body: GraphRetrieveRequest,
    request: Request,
    _: None = Depends(_resolve_active_kb),
) -> GraphRetrieveResponse:
    """Run Ask-equivalent GRAPH retrieval and return the scored subgraph."""
    from akos.domain.ports.graph import Edge

    orchestrator = build_orchestrator_for_request(kb_id, request)
    graph = orchestrator.deps.graph
    retrieval = orchestrator.deps.retrieval
    retrieval.warm_index()
    detail = retrieval.search_graph_detail(body.query.strip(), top_k=body.top_k)
    entities_map = dict(graph.list_entities())

    hits = [
        GraphRetrieveHitResponse(
            score=item.score,
            snippet=item.snippet,
            claim_id=item.claim_id,
            entity_id=item.src,
            src=item.src,
            dst=item.dst,
            predicate=item.predicate,
        )
        for item in detail
    ]

    edge_responses: list = []
    seen_edges: set[tuple[str, str, str]] = set()
    entity_ids: set[str] = set()
    for item in detail:
        entity_ids.add(item.src)
        entity_ids.add(item.dst)
        key = (item.src, item.predicate, item.dst)
        if key in seen_edges:
            continue
        seen_edges.add(key)
        edge_responses.append(
            to_edge_response(
                graph,
                Edge(src=item.src, predicate=item.predicate, dst=item.dst, props={}),
                entities_map,
            )
        )

    entities = []
    for entity_id in sorted(entity_ids):
        props = entities_map.get(entity_id)
        if props is None:
            entities.append(GraphEntityResponse(id=entity_id, type="Concept", name=entity_id))
        else:
            entities.append(to_entity_response(entity_id, props))

    return GraphRetrieveResponse(
        query=body.query.strip(),
        hit_count=len(hits),
        hits=hits,
        entities=entities,
        edges=edge_responses,
    )
