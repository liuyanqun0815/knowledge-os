from __future__ import annotations

import re
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any

from agents.memory_agent import service as memory_agent
from agents.retriever_agent import service as retriever_agent
from agents.verification_agent import service as verification_agent
from compiler.chunk_service import index_source_chunks
from infra.settings import get_settings
from knowledge.models import Answer
from orchestrator.state import AskState, IngestState
from orchestrator.synthesis import build_synthesis_context, synthesize_answer
from retrieval.fusion import fuse_hits, route_fusion_weights
from retrieval.ports import Hit, RetrievalMode
_YEAR_PATTERN = re.compile(r"(20\d{2})年?")
_TEMPORAL_WORDS = ("当时", "那时", "之前")
_PROCEDURE_KEYWORDS = ("怎么做", "流程", "步骤", "怎么走")


def store_source_node(state: IngestState, deps: Any) -> dict:
    try:
        stored = deps.files.store(
            state["file_path"],
            state["source_type"],
            knowledge_base_id=deps.knowledge_base_id,
        )
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
    report = deps.compiler.ingest(
        source_id,
        staging=staging,
        llm_client=deps.llm_client,
        domain=deps.domain,
    )
    return {"report": report}


def index_chunks_node(state: IngestState, deps: Any) -> dict:
    if state.get("error"):
        return {}
    source_id = state.get("source_id")
    if not source_id:
        return {"error": "no source_id", "chunk_report": None}
    settings = get_settings()
    chunk_retrieval = getattr(deps, "chunk_retrieval", None)
    report = index_source_chunks(deps.knowledge, chunk_retrieval, source_id, settings)
    if report.errors:
        return {"chunk_report": report, "error": report.errors[0]}
    return {"chunk_report": report}


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
    procedure = None
    if any(keyword in question for keyword in _PROCEDURE_KEYWORDS):
        procedure = deps.memory.get_procedure(question)
    return {"retrieval_mode": mode, "procedure": procedure}


def retrieve_node(state: AskState, deps: Any) -> dict:
    question = state.get("normalized_question") or state["question"]
    mode = state.get("retrieval_mode") or RetrievalMode.HYBRID
    settings = get_settings()
    claim_hits = retriever_agent.retrieve(deps.retrieval, question, mode, state.get("as_of"))
    chunk_hits: list[Hit] = []
    chunk_retrieval = getattr(deps, "chunk_retrieval", None)
    if settings.chunk_index and chunk_retrieval is not None:
        chunk_hits = chunk_retrieval.search(question, {"top_k": settings.retrieval_top_k})
    fused_hits = fuse_hits(claim_hits, chunk_hits, claim_weight=route_fusion_weights(question))
    mode_value = mode.value if isinstance(mode, RetrievalMode) else str(mode)
    return {
        "hits": fused_hits,
        "chunk_hits": chunk_hits,
        "trace": [
            {
                "node": "retrieve",
                "hit_count": len(fused_hits),
                "claim_hits": len(claim_hits),
                "chunk_hits": len(chunk_hits),
                "retrieval_mode": mode_value,
            }
        ],
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


def _chunk_ids_from_hits(deps: Any, hits: list[Hit]) -> list[str]:
    chunk_ids: list[str] = []
    for hit in hits:
        if hit.hit_type != "chunk" or not hit.chunk_id:
            continue
        chunk = deps.knowledge.get_chunk(hit.chunk_id)
        if chunk is None or chunk.status != "active":
            continue
        if hit.chunk_id not in chunk_ids:
            chunk_ids.append(hit.chunk_id)
    return chunk_ids


def verify_node(state: AskState, deps: Any) -> dict:
    hits = state.get("hits") or []
    chunk_hits = state.get("chunk_hits") or []
    as_of = state.get("as_of")
    claim_ids = _claim_ids_from_hits(deps, hits, as_of)
    chunk_ids = _chunk_ids_from_hits(deps, hits)
    if not chunk_ids:
        chunk_ids = _chunk_ids_from_hits(deps, chunk_hits)
    verification = None
    if claim_ids:
        verification = verification_agent.verify_claims(
            deps.verification,
            deps.knowledge,
            deps.evidence,
            claim_ids,
        )
    trace_entry = {
        "node": "verify",
        "claim_ids": claim_ids,
        "chunk_ids": chunk_ids,
        "verification_status": verification.verification_status if verification else "verified",
    }
    if not claim_ids and not chunk_ids:
        return {"claim_ids": [], "chunk_ids": [], "verification": verification, "trace": [trace_entry]}
    return {"claim_ids": claim_ids, "chunk_ids": chunk_ids, "verification": verification, "trace": [trace_entry]}


def explain_node(state: AskState, deps: Any) -> dict:
    verification = state.get("verification")
    claim_ids = state.get("claim_ids") or []
    chunk_ids = state.get("chunk_ids") or []
    if verification is None:
        effective_ids = claim_ids
    elif verification.verification_status == "partial":
        effective_ids = claim_ids
    else:
        effective_ids = verification.verified_claim_ids
    return {"claim_ids": effective_ids, "chunk_ids": chunk_ids}


def synthesize_node(state: AskState, deps: Any) -> dict:
    settings = get_settings()
    claim_ids = state.get("claim_ids") or []
    chunk_ids = state.get("chunk_ids") or []
    question = state.get("normalized_question") or state["question"]
    if not settings.ask_synthesis:
        return {"synthesis_skipped_reason": "disabled"}
    if not claim_ids and not chunk_ids:
        return {"synthesis_skipped_reason": "no_context"}
    context = build_synthesis_context(
        question=question,
        claim_ids=claim_ids,
        chunk_ids=chunk_ids,
        deps=deps,
        settings=settings,
    )
    result = synthesize_answer(context, deps.llm_client, settings)
    if result is None:
        return {"synthesis_skipped_reason": "failed"}
    return {
        "synthesis_text": result["answer"],
        "synthesis_citations": result.get("citations", []),
        "synthesis_skipped_reason": None,
    }


def _retrieval_mode_value(mode: RetrievalMode | None) -> str:
    if mode is None:
        return RetrievalMode.HYBRID.value
    return mode.value if isinstance(mode, RetrievalMode) else str(mode)


def _format_procedure_steps(procedure: Any) -> str:
    lines = [f"流程：{procedure.name}"]
    for step in sorted(procedure.steps, key=lambda item: item.order):
        lines.append(f"{step.order}. {step.description}")
    return "\n".join(lines)


def _procedure_claim_ids(procedure: Any) -> list[str]:
    claim_ids: list[str] = []
    for step in procedure.steps:
        for claim_id in step.claim_refs:
            if claim_id not in claim_ids:
                claim_ids.append(claim_id)
    return claim_ids


def _chunk_citations(deps: Any, chunk_ids: list[str]) -> list[dict]:
    citations: list[dict] = []
    for chunk_id in chunk_ids:
        chunk = deps.knowledge.get_chunk(chunk_id)
        if chunk is None:
            continue
        quote = (chunk.summary or chunk.text)[:120]
        citations.append({"source_id": chunk.source_id, "chunk_id": chunk_id, "quote": quote})
    return citations


def _build_answer(
    *,
    text: str,
    claim_ids: list[str],
    chunk_ids: list[str],
    evidence: list[dict],
    chunk_citations: list[dict],
    confidence: float,
    retrieval_mode: RetrievalMode | None,
    verification_status: str,
    competing_claim_ids: list[str],
    as_of: datetime | None,
    procedure_id: str | None,
    synthesis_used: bool = False,
) -> dict:
    return {
        "answer": Answer(
            text=text,
            claim_ids=claim_ids,
            chunk_ids=chunk_ids,
            evidence=evidence,
            chunk_citations=chunk_citations,
            synthesis_used=synthesis_used,
            confidence=confidence,
            retrieval_mode=_retrieval_mode_value(retrieval_mode),
            verification_status=verification_status,
            competing_claim_ids=competing_claim_ids,
            as_of=as_of,
            procedure_id=procedure_id,
        )
    }


def answer_node(state: AskState, deps: Any) -> dict:
    claim_ids = state.get("claim_ids") or []
    chunk_ids = state.get("chunk_ids") or []
    retrieval_mode = state.get("retrieval_mode")
    as_of = state.get("as_of")
    verification = state.get("verification")
    procedure = state.get("procedure")
    low_confidence_message = deps.domain.low_confidence_message()
    verification_status = verification.verification_status if verification else "verified"
    competing_claim_ids = list(verification.competing_claim_ids) if verification else []
    procedure_id = procedure.id if procedure else None
    synthesis_text = state.get("synthesis_text")
    synthesis_citations = state.get("synthesis_citations") or []

    if synthesis_text:
        evidence = [
            {
                "source_id": item.get("source_id"),
                "quote": item.get("quote"),
                "weight": 1.0,
                "claim_id": item.get("claim_id"),
            }
            for item in synthesis_citations
            if item.get("source_id") and item.get("quote")
        ]
        confidence = verification.adjusted_confidence if verification else 0.75
        if not claim_ids and chunk_ids:
            confidence = min(confidence, 0.7)
        chunk_citations = [
            {
                "source_id": item.get("source_id"),
                "chunk_id": item.get("chunk_id"),
                "quote": item.get("quote"),
            }
            for item in synthesis_citations
            if item.get("chunk_id")
        ] or _chunk_citations(deps, chunk_ids)
        return _build_answer(
            text=synthesis_text,
            claim_ids=claim_ids,
            chunk_ids=chunk_ids,
            evidence=evidence,
            chunk_citations=chunk_citations,
            confidence=confidence,
            retrieval_mode=retrieval_mode,
            verification_status=verification_status,
            competing_claim_ids=competing_claim_ids,
            as_of=as_of,
            procedure_id=procedure_id,
            synthesis_used=True,
        )

    if procedure is not None:
        procedure_claim_ids = _procedure_claim_ids(procedure)
        merged_claim_ids = list(claim_ids)
        for claim_id in procedure_claim_ids:
            if claim_id not in merged_claim_ids:
                merged_claim_ids.append(claim_id)

        answer_parts = [_format_procedure_steps(procedure)]
        claim_texts = []
        for claim_id in merged_claim_ids:
            claim = deps.knowledge.get_claim(claim_id)
            if claim is not None:
                claim_texts.append(deps.domain.format_claim(claim))
        if claim_texts:
            answer_parts.append("。".join(claim_texts))

        evidence = []
        confidence = 0.8
        if merged_claim_ids:
            bundle = deps.evidence.explain(merged_claim_ids)
            evidence = [
                {"source_id": item["source_id"], "quote": item["quote"], "weight": item["weight"]}
                for item in bundle.items
            ]
            confidence = verification.adjusted_confidence if verification else bundle.confidence
            if confidence < 0.4:
                confidence = 0.8

        return _build_answer(
            text="\n".join(answer_parts),
            claim_ids=merged_claim_ids,
            chunk_ids=chunk_ids,
            evidence=evidence,
            chunk_citations=_chunk_citations(deps, chunk_ids),
            confidence=confidence,
            retrieval_mode=retrieval_mode,
            verification_status=verification_status,
            competing_claim_ids=competing_claim_ids,
            as_of=as_of,
            procedure_id=procedure_id,
        )

    if not claim_ids and not chunk_ids:
        return _build_answer(
            text=low_confidence_message,
            claim_ids=[],
            chunk_ids=[],
            evidence=[],
            chunk_citations=[],
            confidence=0.1,
            retrieval_mode=retrieval_mode,
            verification_status=verification_status,
            competing_claim_ids=competing_claim_ids,
            as_of=as_of,
            procedure_id=procedure_id,
        )

    if claim_ids:
        bundle = deps.evidence.explain(claim_ids)
        confidence = verification.adjusted_confidence if verification else bundle.confidence
        if confidence < 0.4 or not bundle.items:
            if chunk_ids:
                chunk_texts = []
                for chunk_id in chunk_ids:
                    chunk = deps.knowledge.get_chunk(chunk_id)
                    if chunk is None:
                        continue
                    chunk_texts.append(chunk.summary or chunk.text[:160])
                if chunk_texts:
                    return _build_answer(
                        text="。".join(chunk_texts),
                        claim_ids=[],
                        chunk_ids=chunk_ids,
                        evidence=[],
                        chunk_citations=_chunk_citations(deps, chunk_ids),
                        confidence=min(confidence if confidence > 0 else 0.5, 0.7),
                        retrieval_mode=retrieval_mode,
                        verification_status=verification_status,
                        competing_claim_ids=competing_claim_ids,
                        as_of=as_of,
                        procedure_id=procedure_id,
                    )
            return _build_answer(
                text=low_confidence_message,
                claim_ids=[],
                chunk_ids=[],
                evidence=[],
                chunk_citations=[],
                confidence=confidence if confidence > 0 else 0.1,
                retrieval_mode=retrieval_mode,
                verification_status=verification_status,
                competing_claim_ids=competing_claim_ids,
                as_of=as_of,
                procedure_id=procedure_id,
            )

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
        return _build_answer(
            text=answer_text,
            claim_ids=claim_ids,
            chunk_ids=chunk_ids,
            evidence=evidence,
            chunk_citations=_chunk_citations(deps, chunk_ids),
            confidence=confidence,
            retrieval_mode=retrieval_mode,
            verification_status=verification_status,
            competing_claim_ids=competing_claim_ids,
            as_of=as_of,
            procedure_id=procedure_id,
        )

    chunk_texts = []
    for chunk_id in chunk_ids:
        chunk = deps.knowledge.get_chunk(chunk_id)
        if chunk is None:
            continue
        chunk_texts.append(chunk.summary or chunk.text[:160])
    if not chunk_texts:
        return _build_answer(
            text=low_confidence_message,
            claim_ids=[],
            chunk_ids=[],
            evidence=[],
            chunk_citations=[],
            confidence=0.1,
            retrieval_mode=retrieval_mode,
            verification_status=verification_status,
            competing_claim_ids=competing_claim_ids,
            as_of=as_of,
            procedure_id=procedure_id,
        )
    return _build_answer(
        text="。".join(chunk_texts),
        claim_ids=[],
        chunk_ids=chunk_ids,
        evidence=[],
        chunk_citations=_chunk_citations(deps, chunk_ids),
        confidence=0.65,
        retrieval_mode=retrieval_mode,
        verification_status=verification_status,
        competing_claim_ids=competing_claim_ids,
        as_of=as_of,
        procedure_id=procedure_id,
    )


def remember_node(state: AskState, deps: Any) -> dict:
    answer = state.get("answer")
    session_id = state.get("session_id")
    if answer and session_id:
        memory_agent.remember(deps.memory, session_id, {"q": state["question"], "a": answer.text})
    return {}
