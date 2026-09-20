from __future__ import annotations

from typing import Any

from akos.interfaces.api.admin_api.schemas import GraphEdgeResponse, GraphEntityResponse
from akos.application.ingest.service import _entity_id
from akos.domain.ports.graph import Edge, GraphPort

# Topic 结构边：非 Claim，按 Topic.status 判断是否生效
_STRUCTURAL_PREDICATES = frozenset({"涵盖", "包含段落"})


def entity_name(graph: GraphPort, entity_id: str, entities: dict[str, dict[str, Any]] | None = None) -> str:
    entity = entities.get(entity_id) if entities is not None else graph.get_entity(entity_id)
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


def to_edge_response(
    graph: GraphPort,
    edge: Edge,
    entities: dict[str, dict[str, Any]] | None = None,
) -> GraphEdgeResponse:
    return GraphEdgeResponse(
        src=edge.src,
        predicate=edge.predicate,
        dst=edge.dst,
        src_name=entity_name(graph, edge.src, entities),
        dst_name=entity_name(graph, edge.dst, entities),
    )


def active_claim_relation_keys(knowledge: Any) -> set[tuple[str, str, str]]:
    keys: set[tuple[str, str, str]] = set()
    if knowledge is None:
        return keys
    for claim in knowledge.get_claims_by_status("active"):
        src = _entity_id(claim.subject, claim.subject_type)
        dst = _entity_id(claim.object, claim.object_type)
        keys.add((src, claim.predicate, dst))
    return keys


def _topic_is_active(props: dict[str, Any] | None) -> bool:
    if not props:
        return False
    if props.get("type") != "Topic":
        return False
    return props.get("status") != "stale"


def edge_is_active(
    edge: Edge,
    active_keys: set[tuple[str, str, str]],
    entities: dict[str, dict[str, Any]],
) -> bool:
    key = (edge.src, edge.predicate, edge.dst)
    if key in active_keys:
        return True
    if edge.predicate not in _STRUCTURAL_PREDICATES:
        return False
    return _topic_is_active(entities.get(edge.src))


def _is_stale_topic(props: dict[str, Any]) -> bool:
    return props.get("type") == "Topic" and props.get("status") == "stale"


def _load_graph_maps(graph: GraphPort) -> tuple[dict[str, dict[str, Any]], list[Edge]]:
    entities = dict(graph.list_entities())
    list_relations = getattr(graph, "list_relations", None)
    if callable(list_relations):
        relations = list(list_relations())
    else:
        relations = []
        for entity_id in entities:
            relations.extend(graph.neighbors(entity_id))
    return entities, relations


def collect_active_entity_ids(
    graph: GraphPort,
    knowledge: Any,
    *,
    entities: dict[str, dict[str, Any]] | None = None,
    relations: list[Edge] | None = None,
) -> set[str]:
    if entities is None or relations is None:
        entities, relations = _load_graph_maps(graph)
    active_keys = active_claim_relation_keys(knowledge)
    entity_ids: set[str] = set()
    for src, _pred, dst in active_keys:
        entity_ids.add(src)
        entity_ids.add(dst)

    for entity_id, props in entities.items():
        if not _topic_is_active(props):
            continue
        entity_ids.add(entity_id)

    for edge in relations:
        if not edge_is_active(edge, active_keys, entities):
            continue
        if edge.predicate in _STRUCTURAL_PREDICATES and not _topic_is_active(entities.get(edge.src)):
            continue
        if edge.predicate in _STRUCTURAL_PREDICATES or edge.src in entity_ids:
            entity_ids.add(edge.src)
            entity_ids.add(edge.dst)
    return entity_ids


def filter_edges(
    graph: GraphPort,
    edges: list[Edge],
    *,
    knowledge: Any,
    active_only: bool,
    entities: dict[str, dict[str, Any]] | None = None,
) -> list[Edge]:
    if not active_only:
        return edges
    entity_map = entities if entities is not None else dict(graph.list_entities())
    active_keys = active_claim_relation_keys(knowledge)
    return [edge for edge in edges if edge_is_active(edge, active_keys, entity_map)]


def build_snapshot(
    graph: GraphPort,
    *,
    entity_limit: int,
    edge_limit: int,
    knowledge: Any = None,
    active_only: bool = True,
) -> tuple[list[GraphEntityResponse], list[GraphEdgeResponse], bool, int]:
    entities_map, relations = _load_graph_maps(graph)
    if active_only:
        allowed_ids = collect_active_entity_ids(
            graph,
            knowledge,
            entities=entities_map,
            relations=relations,
        )
        filtered = [
            (entity_id, props)
            for entity_id, props in entities_map.items()
            if entity_id in allowed_ids and not _is_stale_topic(props)
        ]
    else:
        filtered = list(entities_map.items())

    entity_total = len(filtered)
    truncated = entity_total > entity_limit
    limited_entities = filtered[:entity_limit]
    entities = [to_entity_response(entity_id, props) for entity_id, props in limited_entities]
    selected_ids = {entity_id for entity_id, _props in limited_entities}

    active_keys = active_claim_relation_keys(knowledge) if active_only else set()
    edges: list[GraphEdgeResponse] = []
    seen: set[tuple[str, str, str]] = set()
    for edge in relations:
        if edge.src not in selected_ids:
            continue
        if active_only and not edge_is_active(edge, active_keys, entities_map):
            continue
        key = (edge.src, edge.predicate, edge.dst)
        if key in seen:
            continue
        seen.add(key)
        edges.append(to_edge_response(graph, edge, entities_map))
        if len(edges) >= edge_limit:
            truncated = True
            break
    return entities, edges, truncated, entity_total


def list_predicates(
    graph: GraphPort,
    *,
    q: str | None = None,
    limit: int = 100,
    knowledge: Any = None,
    active_only: bool = True,
) -> list[str]:
    query = (q or "").strip().lower()
    entities_map, relations = _load_graph_maps(graph)
    active_keys = active_claim_relation_keys(knowledge) if active_only else set()
    predicates: set[str] = set()
    for edge in relations:
        if active_only and not edge_is_active(edge, active_keys, entities_map):
            continue
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
    knowledge: Any = None,
    active_only: bool = True,
) -> list[GraphEntityResponse]:
    query = (q or "").strip().lower()
    predicate_query = (predicate or "").strip().lower()
    if not query and not predicate_query:
        return []

    entities_map, relations = _load_graph_maps(graph)
    allowed_ids = (
        collect_active_entity_ids(graph, knowledge, entities=entities_map, relations=relations)
        if active_only
        else set(entities_map)
    )
    active_keys = active_claim_relation_keys(knowledge) if active_only else set()

    candidate_ids: set[str] | None = None
    if predicate_query:
        candidate_ids = set()
        for edge in relations:
            if active_only and not edge_is_active(edge, active_keys, entities_map):
                continue
            if predicate_query not in edge.predicate.lower():
                continue
            if active_only and edge.src not in allowed_ids and edge.dst not in allowed_ids:
                continue
            candidate_ids.add(edge.src)
            candidate_ids.add(edge.dst)

    results: list[GraphEntityResponse] = []
    for entity_id, props in entities_map.items():
        if active_only and (entity_id not in allowed_ids or _is_stale_topic(props)):
            continue
        if candidate_ids is not None and entity_id not in candidate_ids:
            continue
        response = to_entity_response(entity_id, props)
        if query and query not in response.name.lower() and query not in response.id.lower():
            continue
        results.append(response)

    results.sort(key=lambda item: item.name)
    return results[:limit]
