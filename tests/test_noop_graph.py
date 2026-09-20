from akos.adapters.graph.noop import NoOpGraph


def test_noop_graph_swallows_writes_and_returns_empty():
    graph = NoOpGraph()
    graph.upsert_entity("e1", "Concept", {"name": "银行"})
    graph.upsert_relation("e1", "关联", "e2", {})
    assert graph.list_entities() == []
    assert graph.list_relations() == []
    assert graph.neighbors("e1") == []
    assert graph.get_entity("e1") is None
