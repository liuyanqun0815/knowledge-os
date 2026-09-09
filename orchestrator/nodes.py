from __future__ import annotations

import re
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any

from agents.memory_agent import service as memory_agent
from agents.retriever_agent import service as retriever_agent
from agents.verification_agent import service as verification_agent
from knowledge.models import Answer
from orchestrator.state import AskState, IngestState
from retrieval.ports import Hit, RetrievalMode
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


def _claim_spans_verified(knowledge: Any, evidence: Any, claim_id: str) -> bool:
    bundle = evidence.explain([claim_id])
    if not bundle.items:
        return False
    for item in bundle.items:
        text = knowledge.get_source_text(item["source_id"])
        if text is None or item["quote"] not in text:
            return False
    return True


def verify_sample_node(state: IngestState, deps: Any) -> dict:
    if state.get("error"):
        return {}
    source_id = state.get("source_id")
    if not source_id:
        return {"error": "no source_id for verify_sample", "verify_report": None}

    high_risk = set(deps.domain.high_risk_predicates())
    if not high_risk:
        return {
            "verify_report": {
                "checked": 0,
                "passed": 0,
                "quarantined": 0,
                "failed_claim_ids": [],
            }
        }

    if deps.knowledge.get_source_text(source_id) is None:
        return {"error": "source text not found for verify_sample", "verify_report": None}

    checked = 0
    passed = 0
    quarantined = 0
    failed_claim_ids: list[str] = []

    for claim in deps.knowledge.get_claims_for_source(source_id):
        if claim.predicate not in high_risk:
            continue
        checked += 1
        if _claim_spans_verified(deps.knowledge, deps.evidence, claim.id):
            passed += 1
            continue

        bundle = deps.evidence.explain([claim.id])
        failed_claim_ids.append(claim.id)
        deps.knowledge.add_quarantine(
            "span_mismatch",
            {
                "claim_id": claim.id,
                "source_id": source_id,
                "predicate": claim.predicate,
                "quote": bundle.items[0]["quote"] if bundle.items else None,
            },
        )
        claim.status = "quarantined"
        quarantined += 1

    return {
        "verify_report": {
            "checked": checked,
            "passed": passed,
            "quarantined": quarantined,
            "failed_claim_ids": failed_claim_ids,
        }
    }


def recall_node(state: AskState, deps: Any) -> dict:
    memory_agent.recall(deps.memory, state["question"], state.get("session_id"))
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
    mode = retriever_agent.route_mode(question)
    return {"retrieval_mode": mode}


def retrieve_node(state: AskState, deps: Any) -> dict:
    question = state.get("normalized_question") or state["question"]
    mode = state.get("retrieval_mode") or RetrievalMode.HYBRID
    hits = retriever_agent.retrieve(deps.retrieval, question, mode, state.get("as_of"))
    mode_value = mode.value if isinstance(mode, RetrievalMode) else str(mode)
    return {
        "hits": hits,
        "trace": [{"node": "retrieve", "hit_count": len(hits), "retrieval_mode": mode_value}],
    }


def _resolve_claim_id_for_time(deps: Any, claim_id: str, as_of: datetime | None) -> str | None:
    claim = deps.knowledge.get_claim(claim_id)
    if claim is None:
        return None
    if as_of is None:
        return claim_id if claim.status == "active" else None
    temporal = deps.knowledge.as_of(_ensure_utc(as_of), claim.family_id)
    return temporal.id if temporal is not None else None


def _claim_ids_from_hits(deps: Any, hits: list[Hit], as_of: datetime | None) -> list[str]:
    claim_ids: list[str] = []
    for hit in hits:
        if not hit.claim_id:
            continue
        resolved = _resolve_claim_id_for_time(deps, hit.claim_id, as_of)
        if resolved and resolved not in claim_ids:
            claim_ids.append(resolved)
    return claim_ids


def verify_node(state: AskState, deps: Any) -> dict:
    hits = state.get("hits") or []
    as_of = state.get("as_of")
    claim_ids = _claim_ids_from_hits(deps, hits, as_of)
    if not claim_ids:
        return {"claim_ids": [], "verification": None}
    verification = verification_agent.verify_claims(
        deps.verification,
        deps.knowledge,
        deps.evidence,
        claim_ids,
    )
    trace_entry = {
        "node": "verify",
        "claim_ids": claim_ids,
        "verification_status": verification.verification_status,
    }
    return {"claim_ids": claim_ids, "verification": verification, "trace": [trace_entry]}


def explain_node(state: AskState, deps: Any) -> dict:
    verification = state.get("verification")
    claim_ids = state.get("claim_ids") or []
    if verification is None:
        effective_ids = claim_ids
    elif verification.verification_status == "partial":
        effective_ids = claim_ids
    else:
        effective_ids = verification.verified_claim_ids
    return {"claim_ids": effective_ids}


def _retrieval_mode_value(mode: RetrievalMode | None) -> str:
    if mode is None:
        return RetrievalMode.HYBRID.value
    return mode.value if isinstance(mode, RetrievalMode) else str(mode)


def answer_node(state: AskState, deps: Any) -> dict:
    claim_ids = state.get("claim_ids") or []
    retrieval_mode = state.get("retrieval_mode")
    as_of = state.get("as_of")
    verification = state.get("verification")
    low_confidence_message = deps.domain.low_confidence_message()
    verification_status = verification.verification_status if verification else "verified"
    competing_claim_ids = list(verification.competing_claim_ids) if verification else []

    if not claim_ids:
        return {
            "answer": Answer(
                text=low_confidence_message,
                claim_ids=[],
                evidence=[],
                confidence=0.1,
                retrieval_mode=_retrieval_mode_value(retrieval_mode),
                verification_status=verification_status,
                competing_claim_ids=competing_claim_ids,
                as_of=as_of,
            )
        }

    bundle = deps.evidence.explain(claim_ids)
    confidence = verification.adjusted_confidence if verification else bundle.confidence
    if confidence < 0.4 or not bundle.items:
        return {
            "answer": Answer(
                text=low_confidence_message,
                claim_ids=[],
                evidence=[],
                confidence=confidence if confidence > 0 else 0.1,
                retrieval_mode=_retrieval_mode_value(retrieval_mode),
                verification_status=verification_status,
                competing_claim_ids=competing_claim_ids,
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
            confidence=confidence,
            retrieval_mode=_retrieval_mode_value(retrieval_mode),
            verification_status=verification_status,
            competing_claim_ids=competing_claim_ids,
            as_of=as_of,
        )
    }


def remember_node(state: AskState, deps: Any) -> dict:
    answer = state.get("answer")
    session_id = state.get("session_id")
    if answer and session_id:
        memory_agent.remember(deps.memory, session_id, {"q": state["question"], "a": answer.text})
    return {}
