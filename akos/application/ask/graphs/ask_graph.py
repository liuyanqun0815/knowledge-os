from langgraph.graph import END, StateGraph

import akos.application.ask.nodes as nodes
from akos.application.ask.state import AskState


def build_ask_graph(deps):
    """Build ask graph; node callables resolve via module so reloads pick up new code."""
    graph = StateGraph(AskState)
    graph.add_node("recall", lambda state: nodes.recall_node(state, deps))
    graph.add_node("parse_time", lambda state: nodes.parse_time_node(state, deps))
    graph.add_node("normalize", lambda state: nodes.normalize_node(state, deps))
    graph.add_node("route_mode", lambda state: nodes.route_mode_node(state, deps))
    graph.add_node("retrieve", lambda state: nodes.retrieve_node(state, deps))
    graph.add_node("rerank", lambda state: nodes.rerank_node(state, deps))
    graph.add_node("verify", lambda state: nodes.verify_node(state, deps))
    graph.add_node("explain", lambda state: nodes.explain_node(state, deps))
    graph.add_node("synthesize", lambda state: nodes.synthesize_node(state, deps))
    graph.add_node("answer", lambda state: nodes.answer_node(state, deps))
    graph.add_node("remember", lambda state: nodes.remember_node(state, deps))
    graph.set_entry_point("recall")
    graph.add_edge("recall", "parse_time")
    graph.add_edge("parse_time", "normalize")
    graph.add_edge("normalize", "route_mode")
    graph.add_edge("route_mode", "retrieve")
    graph.add_edge("retrieve", "rerank")
    graph.add_edge("rerank", "verify")
    graph.add_edge("verify", "explain")
    graph.add_edge("explain", "synthesize")
    graph.add_edge("synthesize", "answer")
    graph.add_edge("answer", "remember")
    graph.add_edge("remember", END)
    return graph.compile()
