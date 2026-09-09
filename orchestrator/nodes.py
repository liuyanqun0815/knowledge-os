from __future__ import annotations

from dataclasses import replace
from typing import Any

from knowledge.models import Answer
from orchestrator.state import AskState, IngestState
from retrieval.ports import RetrievalMode

_GRAPH_RELATION_WORDS = ("关系", "关联", "之间", "相关")


def store_source_node(state: IngestState, deps: Any) -> dict:
    try:
        stored = deps.files.store(state["file_path"], state["source_type"])
        source = stored.source
        replaces_source_id = state.get("replaces_source_id")
        if replaces_source_id:
            source = replace(source, replaces_source_id=replaces_source_id)
        source = deps.knowledge.save_source(source)
        deps.knowledge.save_source_text(source.id, stored.text)
        return {"source_id": source.id, "error": None}
    except Exception as exc:
        return {"error": str(exc), "source_id": None}


def compile_node(state: IngestState, deps: Any) -> dict:
    if state.get("error"):
        return {}
    source_id = state.get("source_id")
    if not source_id:
        return {"error": "no source_id", "report": None}
    staging = bool(state.get("replaces_source_id"))
    report = deps.compiler.ingest(source_id, staging=staging)
    return {"report": report}


def evolve_node(state: IngestState, deps: Any) -> dict:
    if state.get("error"):
        return {}
    old_id = state.get("replaces_source_id")
    new_id = state.get("source_id")
    if not old_id or not new_id:
        return {"error": "missing source ids for evolve", "evolve_report": None}
    diff = deps.evolution.diff_sources(old_id, new_id)
    evolve_report = deps.evolution.apply_diff(diff)
    return {"evolve_report": evolve_report}


def recall_node(state: AskState, deps: Any) -> dict:
    deps.memory.recall(state["question"], state.get("session_id"))
    return {}


def normalize_node(state: AskState, deps: Any) -> dict:
    question = state["question"]
    normalized = question
    for alias in deps.domain.get_aliases():
        if alias in normalized:
            normalized = normalized.replace(alias, deps.ontology.normalize_term(alias))
    return {"normalized_question": normalized}


def route_mode_node(state: AskState, deps: Any) -> dict:
    question = state.get("normalized_question") or state["question"]
    if "为什么" in question or "为何" in question:
        mode = RetrievalMode.CLAIM
    elif any(word in question for word in _GRAPH_RELATION_WORDS):
        mode = RetrievalMode.GRAPH
    else:
        mode = RetrievalMode.HYBRID
    return {"retrieval_mode": mode}


def retrieve_node(state: AskState, deps: Any) -> dict:
    question = state.get("normalized_question") or state["question"]
    mode = state.get("retrieval_mode") or RetrievalMode.HYBRID
    hits = deps.retrieval.search(question, mode, {})
    return {"hits": hits}


def explain_node(state: AskState, deps: Any) -> dict:
    hits = state.get("hits") or []
    claim_ids = list(dict.fromkeys(hit.claim_id for hit in hits if hit.claim_id))
    return {"claim_ids": claim_ids}


def _retrieval_mode_value(mode: RetrievalMode | None) -> str:
    if mode is None:
        return RetrievalMode.HYBRID.value
    return mode.value if isinstance(mode, RetrievalMode) else str(mode)


def answer_node(state: AskState, deps: Any) -> dict:
    claim_ids = state.get("claim_ids") or []
    retrieval_mode = state.get("retrieval_mode")
    low_confidence_message = deps.domain.low_confidence_message()

    if not claim_ids:
        return {
            "answer": Answer(
                text=low_confidence_message,
                claim_ids=[],
                evidence=[],
                confidence=0.1,
                retrieval_mode=_retrieval_mode_value(retrieval_mode),
            )
        }

    bundle = deps.evidence.explain(claim_ids)
    if bundle.confidence < 0.4 or not bundle.items:
        return {
            "answer": Answer(
                text=low_confidence_message,
                claim_ids=[],
                evidence=[],
                confidence=bundle.confidence if bundle.confidence > 0 else 0.1,
                retrieval_mode=_retrieval_mode_value(retrieval_mode),
            )
        }

    texts = []
    for claim_id in claim_ids:
        claim = deps.knowledge.get_claim(claim_id)
        if claim is not None:
            texts.append(deps.domain.format_claim(claim))
    answer_text = "。".join(texts) if texts else bundle.conclusion
    evidence = [
        {"source_id": item["source_id"], "quote": item["quote"], "weight": item["weight"]}
        for item in bundle.items
    ]
    return {
        "answer": Answer(
            text=answer_text,
            claim_ids=claim_ids,
            evidence=evidence,
            confidence=bundle.confidence,
            retrieval_mode=_retrieval_mode_value(retrieval_mode),
        )
    }


def remember_node(state: AskState, deps: Any) -> dict:
    answer = state.get("answer")
    session_id = state.get("session_id")
    if answer and session_id:
        deps.memory.remember_episode(session_id, {"q": state["question"], "a": answer.text})
    return {}
