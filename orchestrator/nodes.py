from __future__ import annotations

import re
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any

from knowledge.models import Answer
from orchestrator.state import AskState, IngestState
from retrieval.ports import RetrievalMode

_GRAPH_RELATION_WORDS = ("关系", "关联", "之间", "相关")
_YEAR_PATTERN = re.compile(r"(20\d{2})年?")
_TEMPORAL_WORDS = ("当时", "那时", "之前")


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
    for claim_id in evolve_report.claims_activated:
        claim = deps.knowledge.get_claim(claim_id)
        if claim is not None:
            deps.retrieval.index_claim(claim)
    return {"evolve_report": evolve_report}


def recall_node(state: AskState, deps: Any) -> dict:
    deps.memory.recall(state["question"], state.get("session_id"))
    return {}


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def parse_time_node(state: AskState, deps: Any) -> dict:
    if state.get("as_of") is not None:
        return {}
    question = state["question"]
    match = _YEAR_PATTERN.search(question)
    if match:
        year = int(match.group(1))
        return {"as_of": datetime(year, 6, 30, tzinfo=timezone.utc)}
    if any(word in question for word in _TEMPORAL_WORDS):
        now = datetime.now(timezone.utc)
        return {"as_of": datetime(now.year - 1, 6, 30, tzinfo=timezone.utc)}
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
    as_of = state.get("as_of")
    filters: dict[str, Any] = {}
    if as_of is not None:
        filters["as_of"] = _ensure_utc(as_of)
    hits = deps.retrieval.search(question, mode, filters)
    return {"hits": hits}


def _resolve_claim_id_for_time(deps: Any, claim_id: str, as_of: datetime | None) -> str | None:
    claim = deps.knowledge.get_claim(claim_id)
    if claim is None:
        return None
    if as_of is None:
        return claim_id if claim.status == "active" else None
    temporal = deps.knowledge.as_of(_ensure_utc(as_of), claim.family_id)
    return temporal.id if temporal is not None else None


def explain_node(state: AskState, deps: Any) -> dict:
    hits = state.get("hits") or []
    as_of = state.get("as_of")
    claim_ids: list[str] = []
    for hit in hits:
        if not hit.claim_id:
            continue
        resolved = _resolve_claim_id_for_time(deps, hit.claim_id, as_of)
        if resolved and resolved not in claim_ids:
            claim_ids.append(resolved)
    return {"claim_ids": claim_ids}


def _retrieval_mode_value(mode: RetrievalMode | None) -> str:
    if mode is None:
        return RetrievalMode.HYBRID.value
    return mode.value if isinstance(mode, RetrievalMode) else str(mode)


def answer_node(state: AskState, deps: Any) -> dict:
    claim_ids = state.get("claim_ids") or []
    retrieval_mode = state.get("retrieval_mode")
    as_of = state.get("as_of")
    low_confidence_message = deps.domain.low_confidence_message()

    if not claim_ids:
        return {
            "answer": Answer(
                text=low_confidence_message,
                claim_ids=[],
                evidence=[],
                confidence=0.1,
                retrieval_mode=_retrieval_mode_value(retrieval_mode),
                as_of=as_of,
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
                as_of=as_of,
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
            as_of=as_of,
        )
    }


def remember_node(state: AskState, deps: Any) -> dict:
    answer = state.get("answer")
    session_id = state.get("session_id")
    if answer and session_id:
        deps.memory.remember_episode(session_id, {"q": state["question"], "a": answer.text})
    return {}
