from langgraph.graph import END, StateGraph

from orchestrator.nodes import compile_node, evolve_node, store_source_node, verify_sample_node
from orchestrator.state import IngestState


def _route_after_verify(state: IngestState) -> str:
    if state.get("error"):
        return END
    if state.get("replaces_source_id"):
        return "evolve"
    return END


def build_ingest_graph(deps):
    graph = StateGraph(IngestState)
    graph.add_node("store", lambda state: store_source_node(state, deps))
    graph.add_node("compile", lambda state: compile_node(state, deps))
    graph.add_node("verify_sample", lambda state: verify_sample_node(state, deps))
    graph.add_node("evolve", lambda state: evolve_node(state, deps))
    graph.set_entry_point("store")
    graph.add_edge("store", "compile")
    graph.add_edge("compile", "verify_sample")
    graph.add_conditional_edges(
        "verify_sample",
        _route_after_verify,
        {"evolve": "evolve", END: END},
    )
    graph.add_edge("evolve", END)
    return graph.compile()
