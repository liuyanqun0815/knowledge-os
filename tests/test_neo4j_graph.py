import os
import uuid

import pytest

from akos.adapters.persistence.graph_memory import InMemoryGraph


def test_inmemory_graph_neighbors():
    g = InMemoryGraph()
    g.upsert_entity("e_rule", "RefundRule", {"name": "七天无理由"})
    g.upsert_entity("e_cat", "Category", {"name": "非定制商品"})
    g.upsert_relation("e_rule", "适用类目", "e_cat", {})
    edges = g.neighbors("e_rule", predicates=["适用类目"], depth=1)
    assert len(edges) == 1
    assert edges[0].dst == "e_cat"


def _neo4j_enabled() -> bool:
    return bool(os.getenv("AKOS_NEO4J_URI")) or os.getenv("AKOS_GRAPH_BACKEND", "").lower() == "neo4j"


@pytest.mark.skipif(not _neo4j_enabled(), reason="requires Neo4j (AKOS_NEO4J_URI or AKOS_GRAPH_BACKEND=neo4j)")
def test_neo4j_graph_upsert_and_neighbors():
    from akos.adapters.graph.neo4j import Neo4jGraph
    from infra.settings import Settings

    settings = Settings()
    kb_id = f"test-neo4j-{uuid.uuid4()}"
    graph = Neo4jGraph(
        uri=os.getenv("AKOS_NEO4J_URI", settings.neo4j_uri),
        user=settings.neo4j_user,
        password=settings.neo4j_password,
        knowledge_base_id=kb_id,
    )
    try:
        graph.upsert_entity("e_rule", "RefundRule", {"name": "七天无理由"})
        graph.upsert_entity("e_cat", "Category", {"name": "非定制商品"})
        graph.upsert_relation("e_rule", "适用类目", "e_cat", {})

        edges = graph.neighbors("e_rule", predicates=["适用类目"], depth=1)
        assert len(edges) == 1
        assert edges[0].dst == "e_cat"
    finally:
        graph.close()
