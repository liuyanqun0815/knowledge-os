from langgraph.graph import END, StateGraph

from orchestrator.nodes import (
    answer_node,
    explain_node,
    normalize_node,
    parse_time_node,
    recall_node,
    remember_node,
    retrieve_node,
    route_mode_node,
    verify_node,
)
from orchestrator.state import AskState


def build_ask_graph(deps):
    graph = StateGraph(AskState)
    graph.add_node("recall", lambda state: recall_node(state, deps))
    graph.add_node("parse_time", lambda state: parse_time_node(state, deps))
    graph.add_node("normalize", lambda state: normalize_node(state, deps))
    graph.add_node("route_mode", lambda state: route_mode_node(state, deps))
    graph.add_node("retrieve", lambda state: retrieve_node(state, deps))
    graph.add_node("verify", lambda state: verify_node(state, deps))
    graph.add_node("explain", lambda state: explain_node(state, deps))
    graph.add_node("answer", lambda state: answer_node(state, deps))
    graph.add_node("remember", lambda state: remember_node(state, deps))
    graph.set_entry_point("recall")
    graph.add_edge("recall", "parse_time")
    graph.add_edge("parse_time", "normalize")
    graph.add_edge("normalize", "route_mode")
    graph.add_edge("route_mode", "retrieve")
    graph.add_edge("retrieve", "verify")
    graph.add_edge("verify", "explain")
    graph.add_edge("explain", "answer")
    graph.add_edge("answer", "remember")
    graph.add_edge("remember", END)
    return graph.compile()
