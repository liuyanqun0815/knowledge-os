from graph.memory_repo import InMemoryGraph


def test_upsert_and_neighbors():
    g = InMemoryGraph()
    g.upsert_entity("e_rule", "RefundRule", {"name": "七天无理由"})
    g.upsert_entity("e_cat", "Category", {"name": "非定制商品"})
    g.upsert_relation("e_rule", "适用类目", "e_cat", {})
    edges = g.neighbors("e_rule", predicates=["适用类目"], depth=1)
    assert len(edges) == 1
    assert edges[0].dst == "e_cat"
