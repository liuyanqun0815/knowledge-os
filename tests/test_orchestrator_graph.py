from orchestrator.graphs.ask_graph import build_ask_graph
from orchestrator.graphs.ingest_graph import build_ingest_graph
from orchestrator.state import AskState


def test_ingest_graph_is_langgraph_stategraph(build_orchestrator_deps):
    deps = build_orchestrator_deps()
    graph = build_ingest_graph(deps)
    assert graph.get_graph().nodes


def test_ask_graph_routes_low_confidence(build_orchestrator_deps):
    deps = build_orchestrator_deps()
    graph = build_ask_graph(deps)
    result: AskState = graph.invoke(
        {
            "question": "今天天气怎么样？",
            "session_id": "s1",
            "as_of": None,
            "trace": [],
        }
    )
    assert result["answer"] is not None
    assert result["answer"].confidence < 0.4
