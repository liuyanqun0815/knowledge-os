from langgraph.graph import END, StateGraph

from orchestrator.nodes import compile_node, store_source_node
from orchestrator.state import IngestState


def build_ingest_graph(deps):
    graph = StateGraph(IngestState)
    graph.add_node("store", lambda state: store_source_node(state, deps))
    graph.add_node("compile", lambda state: compile_node(state, deps))
    graph.set_entry_point("store")
    graph.add_edge("store", "compile")
    graph.add_edge("compile", END)
    return graph.compile()
