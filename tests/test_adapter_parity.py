import os
import uuid

import pytest

from akos.adapters.persistence.graph_memory import InMemoryGraph
from akos.domain.ports.graph import Edge
from tests.conftest import pg_enabled

GOLDEN_ENTITIES = (
    ("e_rule", "RefundRule", {"name": "七天无理由"}),
    ("e_cat", "Category", {"name": "非定制商品"}),
)
GOLDEN_RELATION = ("e_rule", "适用类目", "e_cat", {})
GOLDEN_QUERY = ("e_rule", ["适用类目"], 1)


def _run_golden_set(graph) -> list[Edge]:
    for entity_id, entity_type, props in GOLDEN_ENTITIES:
        graph.upsert_entity(entity_id, entity_type, props)
    src, predicate, dst, props = GOLDEN_RELATION
    graph.upsert_relation(src, predicate, dst, props)
    entity_id, predicates, depth = GOLDEN_QUERY
    return graph.neighbors(entity_id, predicates=predicates, depth=depth)


def _normalize_edges(edges: list[Edge]) -> list[tuple[str, str, str]]:
    return sorted((edge.src, edge.predicate, edge.dst) for edge in edges)


def test_inmemory_golden_set():
    edges = _run_golden_set(InMemoryGraph())
    assert _normalize_edges(edges) == [("e_rule", "适用类目", "e_cat")]


@pytest.mark.skipif(not pg_enabled(), reason="requires AKOS_USE_PG=true")
def test_pg_graph_parity_with_inmemory(pg_kb_repo, pg_engine):
    from akos.adapters.persistence.pg_graph import PgGraph

    memory_graph = InMemoryGraph()
    kb = pg_kb_repo.create(name="adapter-parity", domain_type="ecommerce_cs", description="")
    pg_graph = PgGraph(pg_engine, kb.id)

    memory_edges = _run_golden_set(memory_graph)
    pg_edges = _run_golden_set(pg_graph)

    assert _normalize_edges(memory_edges) == _normalize_edges(pg_edges)
    assert _normalize_edges(pg_edges) == [("e_rule", "适用类目", "e_cat")]


def _neo4j_backend_enabled() -> bool:
    return os.getenv("AKOS_GRAPH_BACKEND", "").lower() == "neo4j"


@pytest.mark.skipif(not _neo4j_backend_enabled(), reason="requires AKOS_GRAPH_BACKEND=neo4j")
def test_neo4j_graph_parity_with_inmemory():
    from akos.adapters.graph.neo4j import Neo4jGraph
    from infra.settings import Settings

    memory_graph = InMemoryGraph()
    settings = Settings()
    kb_id = f"test-parity-{uuid.uuid4()}"
    neo4j_graph = Neo4jGraph(
        uri=os.getenv("AKOS_NEO4J_URI", settings.neo4j_uri),
        user=settings.neo4j_user,
        password=settings.neo4j_password,
        knowledge_base_id=kb_id,
    )
    try:
        memory_edges = _run_golden_set(memory_graph)
        neo4j_edges = _run_golden_set(neo4j_graph)
        assert _normalize_edges(memory_edges) == _normalize_edges(neo4j_edges)
        assert _normalize_edges(neo4j_edges) == [("e_rule", "适用类目", "e_cat")]
    finally:
        neo4j_graph.close()
