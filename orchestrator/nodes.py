from __future__ import annotations

from typing import Any

from knowledge.models import Answer
from orchestrator.state import AskState, IngestState
from retrieval.ports import RetrievalMode

_GRAPH_RELATION_WORDS = ("关系", "关联", "之间", "相关")
_ALIAS_CANDIDATES = ("7天无理由", "七天无理由退货", "无理由退货", "七天无理由")


def store_source_node(state: IngestState, deps: Any) -> dict:
    try:
        stored = deps.files.store(state["file_path"], state["source_type"])
        source = deps.knowledge.save_source(stored.source)
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
    report = deps.compiler.ingest(source_id)
    return {"report": report}


def recall_node(state: AskState, deps: Any) -> dict:
    deps.memory.recall(state["question"], state.get("session_id"))
    return {}


def normalize_node(state: AskState, deps: Any) -> dict:
    question = state["question"]
    normalized = question
    for alias in _ALIAS_CANDIDATES:
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


def _claim_to_text(deps: Any, claim_id: str) -> str | None:
    claim = deps.knowledge.get_claim(claim_id)
    if claim is None:
        return None
    if claim.predicate == "排除":
        return f"{claim.object}不适用{claim.subject}"
    if claim.predicate == "适用类目":
        return f"{claim.subject}适用类目为{claim.object}"
    if claim.predicate == "运费承担方":
        return f"{claim.subject}运费承担方为{claim.object}"
    return f"{claim.subject}{claim.predicate}{claim.object}"


def _retrieval_mode_value(mode: RetrievalMode | None) -> str:
    if mode is None:
        return RetrievalMode.HYBRID.value
    return mode.value if isinstance(mode, RetrievalMode) else str(mode)


def answer_node(state: AskState, deps: Any) -> dict:
    claim_ids = state.get("claim_ids") or []
    retrieval_mode = state.get("retrieval_mode")

    if not claim_ids:
        return {
            "answer": Answer(
                text="依据不足，无法根据现有政策回答该问题。",
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
                text="依据不足，无法根据现有政策回答该问题。",
                claim_ids=[],
                evidence=[],
                confidence=bundle.confidence if bundle.confidence > 0 else 0.1,
                retrieval_mode=_retrieval_mode_value(retrieval_mode),
            )
        }

    texts = [text for claim_id in claim_ids if (text := _claim_to_text(deps, claim_id))]
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
