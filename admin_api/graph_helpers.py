from __future__ import annotations

from typing import Any

from admin_api.schemas import GraphEdgeResponse, GraphEntityResponse
from graph.ports import Edge, GraphPort


def entity_name(graph: GraphPort, entity_id: str) -> str:
    entity = graph.get_entity(entity_id)
    if entity is None:
        return entity_id
    name = entity.get("name")
    return name if isinstance(name, str) and name else entity_id


def entity_type(props: dict[str, Any]) -> str:
    value = props.get("type")
    return value if isinstance(value, str) and value else "Concept"


def to_entity_response(entity_id: str, props: dict[str, Any]) -> GraphEntityResponse:
    name = props.get("name")
    return GraphEntityResponse(
        id=entity_id,
        type=entity_type(props),
        name=name if isinstance(name, str) and name else entity_id,
    )


def to_edge_response(graph: GraphPort, edge: Edge) -> GraphEdgeResponse:
    return GraphEdgeResponse(
        src=edge.src,
        predicate=edge.predicate,
        dst=edge.dst,
        src_name=entity_name(graph, edge.src),
        dst_name=entity_name(graph, edge.dst),
    )


def build_snapshot(
    graph: GraphPort,
    *,
    entity_limit: int,
    edge_limit: int,
) -> tuple[list[GraphEntityResponse], list[GraphEdgeResponse], bool, int]:
    raw_entities = graph.list_entities()
    entity_total = len(raw_entities)
    truncated = len(raw_entities) > entity_limit
    entities = [to_entity_response(entity_id, props) for entity_id, props in raw_entities[:entity_limit]]

    edges: list[GraphEdgeResponse] = []
    seen: set[tuple[str, str, str]] = set()
    for entity in entities:
        for edge in graph.neighbors(entity.id):
            key = (edge.src, edge.predicate, edge.dst)
            if key in seen:
                continue
            seen.add(key)
            edges.append(to_edge_response(graph, edge))
            if len(edges) >= edge_limit:
                truncated = True
                return entities, edges, truncated, entity_total
    return entities, edges, truncated, entity_total


def list_predicates(graph: GraphPort, *, q: str | None = None, limit: int = 100) -> list[str]:
    query = (q or "").strip().lower()
    predicates: set[str] = set()
    for entity_id, _props in graph.list_entities():
        for edge in graph.neighbors(entity_id):
            if query and query not in edge.predicate.lower():
                continue
            predicates.add(edge.predicate)
            if len(predicates) >= limit:
                return sorted(predicates)
    return sorted(predicates)


def search_entities(
    graph: GraphPort,
    *,
    q: str | None,
    predicate: str | None,
    limit: int,
) -> list[GraphEntityResponse]:
    query = (q or "").strip().lower()
    predicate_query = (predicate or "").strip().lower()
    if not query and not predicate_query:
        return []

    entities_map = dict(graph.list_entities())
    candidate_ids: set[str] | None = None
    if predicate_query:
        candidate_ids = set()
        for entity_id in entities_map:
            for edge in graph.neighbors(entity_id):
                if predicate_query in edge.predicate.lower():
                    candidate_ids.add(entity_id)
                    candidate_ids.add(edge.dst)

    results: list[GraphEntityResponse] = []
    for entity_id, props in entities_map.items():
        if candidate_ids is not None and entity_id not in candidate_ids:
            continue
        response = to_entity_response(entity_id, props)
        if query and query not in response.name.lower() and query not in response.id.lower():
            continue
        results.append(response)

    results.sort(key=lambda item: item.name)
    return results[:limit]
