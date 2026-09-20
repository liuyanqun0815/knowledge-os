from __future__ import annotations

import re
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any

from akos.application.ask import memory_ops as memory_agent
from akos.application.ask import retrieve as retriever_agent
from akos.application.ask import verification as verification_agent
from akos.application.ingest.chunk_service import index_source_chunks
from infra.settings import get_settings
from akos.domain.models.knowledge import Answer
from akos.application.ask.question_rewrite import (
    collect_domain_terms,
    try_llm_rewrite,
    try_rule_rewrite,
)
from akos.application.ask.state import AskState, IngestState
from akos.application.ask.synthesis import build_synthesis_context, synthesize_answer
from akos.application.ask.trace_utils import (
    serialize_chunks_for_trace,
    serialize_hits_for_trace,
    trace_step,
)
from akos.adapters.retrieval.fusion import fuse_hits, route_fusion_weights
from akos.adapters.retrieval.reranker import rerank_content_hits_preserving_claims
from akos.domain.ports.retrieval import Hit, RetrievalMode

_YEAR_PATTERN = re.compile(r"(20\d{2})年?")
_TEMPORAL_WORDS = ("当时", "那时", "之前")
_PROCEDURE_KEYWORDS = ("怎么做", "流程", "步骤", "怎么走")
_RETRIEVE_POOL = ThreadPoolExecutor(max_workers=3, thread_name_prefix="akos-retrieve")


def _node_duration_ms(started: float) -> int:
    return max(0, int((time.perf_counter() - started) * 1000))


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
    started = time.perf_counter()
    session_id = state.get("session_id")
    context = memory_agent.recall(deps.memory, state["question"], session_id)
    episodes = list(context.episodes or [])
    semantics = list(context.semantics or [])
    summary = (
        f"召回 {len(episodes)} 条历史会话" if episodes else ("无会话记忆" if not session_id else "当前会话暂无历史")
    )
    return {
        "recall_episodes": episodes,
        "trace": [
            trace_step(
                "recall",
                summary=summary,
                detail={
                    "session_id": session_id,
                    "episode_count": len(episodes),
                    "episodes": episodes,
                    "semantics": semantics,
                },
                duration_ms=_node_duration_ms(started),
            )
        ],
    }


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def parse_time_node(state: AskState, deps: Any) -> dict:
    started = time.perf_counter()
    result: dict[str, Any] = {}
    if state.get("as_of") is None:
        question = state["question"]
        match = _YEAR_PATTERN.search(question)
        if match:
            year = int(match.group(1))
            result["as_of"] = datetime(year, 6, 30, tzinfo=timezone.utc)
        elif any(word in question for word in _TEMPORAL_WORDS):
            now = datetime.now(timezone.utc)
            result["as_of"] = datetime(now.year - 1, 6, 30, tzinfo=timezone.utc)
    result["trace"] = [
        trace_step(
            "parse_time",
            summary="时间解析",
            duration_ms=_node_duration_ms(started),
        )
    ]
    return result


def normalize_node(state: AskState, deps: Any) -> dict:
    started = time.perf_counter()
    settings = get_settings()
    question = state["question"]
    normalized = question
    replacements: list[dict[str, str]] = []
    methods: list[str] = []
    rewrite_detail: dict[str, Any] = {}

    for alias in deps.domain.get_aliases():
        if alias in normalized:
            canonical = deps.ontology.normalize_term(alias)
            if canonical != alias:
                replacements.append({"from": alias, "to": canonical})
            normalized = normalized.replace(alias, canonical)
    if replacements:
        methods.append("alias")

    episodes = list(state.get("recall_episodes") or [])
    terms = collect_domain_terms(deps.ontology, deps.domain)
    rule_hit = try_rule_rewrite(normalized, episodes=episodes, terms=terms)
    if rule_hit is not None:
        normalized = rule_hit.text
        methods.append("rule")
        rewrite_detail = {
            "anchor": rule_hit.anchor,
            "reason": rule_hit.reason,
        }
    elif settings.ask_normalize_llm and episodes:
        try:
            llm_hit = try_llm_rewrite(
                normalized,
                episodes=episodes,
                llm_client=getattr(deps, "llm_client", None),
            )
        except Exception:
            llm_hit = None
        if llm_hit is not None:
            normalized = llm_hit.text
            methods.append("llm")
            rewrite_detail = {"reason": llm_hit.reason}

    changed = normalized != question
    method = "+".join(methods) if methods else "none"
    summary = "问题已归一化" if changed else "无需归一化"
    if "rule" in methods:
        summary = "规则补全问句"
    elif "llm" in methods:
        summary = "LLM 改写问句"

    return {
        "normalized_question": normalized,
        "trace": [
            trace_step(
                "normalize",
                summary=summary,
                detail={
                    "input": question,
                    "output": normalized,
                    "changed": changed,
                    "method": method,
                    "replacements": replacements,
                    "rewrite": rewrite_detail,
                    "episode_count": len(episodes),
                },
                duration_ms=_node_duration_ms(started),
            )
        ],
    }


def route_mode_node(state: AskState, deps: Any) -> dict:
    started = time.perf_counter()
    question = state.get("normalized_question") or state["question"]
    mode = retriever_agent.route_mode(question)
    procedure = None
    if any(keyword in question for keyword in _PROCEDURE_KEYWORDS):
        procedure = deps.memory.get_procedure(question)
    return {
        "retrieval_mode": mode,
        "procedure": procedure,
        "trace": [
            trace_step(
                "route_mode",
                summary=f"检索模式 {mode.value if isinstance(mode, RetrievalMode) else mode}",
                detail={
                    "retrieval_mode": mode.value if isinstance(mode, RetrievalMode) else str(mode),
                    "procedure_id": procedure.id if procedure is not None else None,
                },
                duration_ms=_node_duration_ms(started),
            )
        ],
    }


def retrieve_node(state: AskState, deps: Any) -> dict:
    started = time.perf_counter()
    question = state.get("normalized_question") or state["question"]
    mode = state.get("retrieval_mode") or RetrievalMode.HYBRID
    settings = get_settings()
    as_of = state.get("as_of")
    chunk_retrieval = getattr(deps, "chunk_retrieval", None)
    wiki_retrieval = getattr(deps, "wiki_retrieval", None)
    run_chunk = bool(settings.chunk_index and chunk_retrieval is not None)
    run_wiki = bool(settings.wiki_compile and wiki_retrieval is not None)

    embed_started = time.perf_counter()
    query_embedding: list[float] | None = None
    embedder = getattr(deps.retrieval, "_embedder", None)
    if embedder is None and chunk_retrieval is not None:
        embedder = getattr(chunk_retrieval, "_embedder", None)
    if embedder is not None:
        query_embedding = embedder.embed([question])[0]
    embed_ms = _node_duration_ms(embed_started)

    def _search_claims() -> tuple[list[Hit], int]:
        t0 = time.perf_counter()
        hits = retriever_agent.retrieve(
            deps.retrieval,
            question,
            mode,
            as_of,
            query_embedding=query_embedding,
            top_k=settings.retrieval_top_k,
        )
        return hits, _node_duration_ms(t0)

    def _search_chunks() -> tuple[list[Hit], int]:
        t0 = time.perf_counter()
        if not run_chunk:
            return [], _node_duration_ms(t0)
        filters: dict[str, Any] = {
            "top_k": settings.retrieval_top_k,
            "min_score": settings.chunk_min_score,
        }
        if query_embedding is not None:
            filters["query_embedding"] = query_embedding
        hits = chunk_retrieval.search(question, filters)
        return hits, _node_duration_ms(t0)

    def _search_wiki() -> tuple[list[Hit], int]:
        t0 = time.perf_counter()
        if not run_wiki:
            return [], _node_duration_ms(t0)
        hits = wiki_retrieval.search(question, top_k=settings.retrieval_top_k)
        return hits, _node_duration_ms(t0)

    # One query embedding → Claim/Chunk/Wiki lanes in parallel (PG similarity is cheap).
    claim_future = _RETRIEVE_POOL.submit(_search_claims)
    chunk_future = _RETRIEVE_POOL.submit(_search_chunks)
    wiki_future = _RETRIEVE_POOL.submit(_search_wiki)
    claim_hits, claim_ms = claim_future.result()
    chunk_hits, chunk_ms = chunk_future.result()
    wiki_hits, wiki_ms = wiki_future.result()

    fuse_started = time.perf_counter()
    if wiki_hits:
        fused_hits = fuse_hits(
            claim_hits,
            chunk_hits,
            wiki_hits,
            claim_weight=settings.retrieval_claim_weight,
            wiki_weight=settings.retrieval_wiki_weight,
            chunk_weight=settings.retrieval_chunk_weight,
        )
    else:
        fused_hits = fuse_hits(claim_hits, chunk_hits, claim_weight=route_fusion_weights(question))
    fuse_ms = _node_duration_ms(fuse_started)

    mode_value = mode.value if isinstance(mode, RetrievalMode) else str(mode)
    duration_ms = _node_duration_ms(started)
    parallel_ms = max(claim_ms, chunk_ms, wiki_ms)
    return {
        "hits": fused_hits,
        "chunk_hits": chunk_hits,
        "wiki_hits": wiki_hits,
        "trace": [
            trace_step(
                "retrieve",
                summary=(
                    f"命中 {len(fused_hits)} 条"
                    f"（Claim {len(claim_hits)} / Wiki {len(wiki_hits)} / Chunk {len(chunk_hits)}）；"
                    f" embed {embed_ms}ms / parallel {parallel_ms}ms"
                    f" (claim {claim_ms}ms / chunk {chunk_ms}ms / wiki {wiki_ms}ms)"
                    f" / fuse {fuse_ms}ms"
                ),
                detail={
                    "hit_count": len(fused_hits),
                    "claim_hits": len(claim_hits),
                    "wiki_hits": len(wiki_hits),
                    "chunk_hits": len(chunk_hits),
                    "retrieval_mode": mode_value,
                    "parallel": True,
                    "shared_query_embedding": query_embedding is not None,
                    "embed_ms": embed_ms,
                    "claim_ms": claim_ms,
                    "chunk_ms": chunk_ms,
                    "wiki_ms": wiki_ms,
                    "parallel_ms": parallel_ms,
                    "fuse_ms": fuse_ms,
                    "fused_hits": serialize_hits_for_trace(fused_hits, deps.knowledge),
                    "claim_hit_items": serialize_hits_for_trace(claim_hits, deps.knowledge),
                    "wiki_hit_items": serialize_hits_for_trace(wiki_hits, deps.knowledge),
                    "chunk_hit_items": serialize_hits_for_trace(chunk_hits, deps.knowledge),
                },
                duration_ms=duration_ms,
            )
        ],
    }


def rerank_node(state: AskState, deps: Any) -> dict:
    """Rerank chunk/wiki hits only; keep claim hits ahead for downstream synthesis."""
    started = time.perf_counter()
    settings = get_settings()
    question = state.get("normalized_question") or state["question"]
    hits = list(state.get("hits") or [])
    reranker = getattr(deps, "reranker", None)
    if reranker is None and settings.rerank_enabled:
        from akos.bootstrap import _get_shared_reranker

        reranker = _get_shared_reranker(settings)
        try:
            deps.reranker = reranker
        except Exception:
            pass
    enabled = bool(settings.rerank_enabled and reranker is not None and hits)

    if not enabled:
        return {
            "hits": hits,
            "trace": [
                trace_step(
                    "rerank",
                    status="skipped",
                    summary="重排序已跳过",
                    detail={
                        "rerank_enabled": bool(settings.rerank_enabled),
                        "reranker_loaded": reranker is not None,
                        "input_count": len(hits),
                        "skipped_reason": (
                            "disabled"
                            if not settings.rerank_enabled
                            else "no_reranker" if reranker is None else "no_hits"
                        ),
                    },
                    duration_ms=_node_duration_ms(started),
                )
            ],
        }

    reranked_hits = rerank_content_hits_preserving_claims(
        question,
        hits,
        reranker,
        settings,
        knowledge=deps.knowledge,
    )
    return {
        "hits": reranked_hits,
        "trace": [
            trace_step(
                "rerank",
                summary=(
                    f"重排序完成：输入 {len(hits)} → 输出 {len(reranked_hits)} " f"（仅 chunk/wiki，Claim 保持前置）"
                ),
                detail={
                    "rerank_enabled": True,
                    "input_count": len(hits),
                    "output_count": len(reranked_hits),
                    "rerank_top_n": settings.rerank_top_n,
                    "rerank_min_score": settings.rerank_min_score,
                    "input_hits": serialize_hits_for_trace(hits, deps.knowledge),
                    "output_hits": serialize_hits_for_trace(reranked_hits, deps.knowledge),
                },
                duration_ms=_node_duration_ms(started),
            )
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


def _wiki_pages_from_hits(hits: list[Hit], *, limit: int = 5) -> list[dict[str, Any]]:
    pages: list[dict[str, Any]] = []
    seen: set[str] = set()
    for hit in hits:
        if hit.hit_type != "wiki":
            continue
        key = hit.ref_id or hit.path or hit.snippet or ""
        if not key or key in seen:
            continue
        seen.add(key)
        pages.append(
            {
                "title": hit.title or hit.ref_id or "",
                "excerpt": hit.snippet or "",
                "content": hit.content or hit.snippet or "",
                "path": hit.path or "",
                "links": [],
                "ref_id": hit.ref_id,
            }
        )
        if len(pages) >= limit:
            break
    return pages


def verify_node(state: AskState, deps: Any) -> dict:
    started = time.perf_counter()
    hits = state.get("hits") or []
    chunk_hits = state.get("chunk_hits") or []
    wiki_hits = state.get("wiki_hits") or []
    as_of = state.get("as_of")
    claim_ids = _claim_ids_from_hits(deps, hits, as_of)
    chunk_ids = _chunk_ids_from_hits(deps, hits)
    if not chunk_ids:
        chunk_ids = _chunk_ids_from_hits(deps, chunk_hits)
    wiki_pages = _wiki_pages_from_hits(hits)
    if not wiki_pages:
        wiki_pages = _wiki_pages_from_hits(wiki_hits)
    verification = None
    if claim_ids:
        verification = verification_agent.verify_claims(
            deps.verification,
            deps.knowledge,
            deps.evidence,
            claim_ids,
        )
    verification_status = verification.verification_status if verification else "verified"
    trace_entry = trace_step(
        "verify",
        status="skipped" if not claim_ids and not chunk_ids and not wiki_pages else "ok",
        summary=(
            f"核验 {verification_status}，"
            f"{len(claim_ids)} 条 Claim / {len(wiki_pages)} 页 Wiki / {len(chunk_ids)} 条 Chunk"
            if claim_ids or chunk_ids or wiki_pages
            else "无可用 Claim/Wiki/Chunk，跳过核验"
        ),
        detail={
            "claim_ids": claim_ids,
            "chunk_ids": chunk_ids,
            "wiki_pages": wiki_pages,
            "verification_status": verification_status,
            "chunks": serialize_chunks_for_trace(deps.knowledge, chunk_ids),
        },
        duration_ms=_node_duration_ms(started),
    )
    if not claim_ids and not chunk_ids and not wiki_pages:
        return {
            "claim_ids": [],
            "chunk_ids": [],
            "wiki_pages": [],
            "verification": verification,
            "trace": [trace_entry],
        }
    return {
        "claim_ids": claim_ids,
        "chunk_ids": chunk_ids,
        "wiki_pages": wiki_pages,
        "verification": verification,
        "trace": [trace_entry],
    }


def explain_node(state: AskState, deps: Any) -> dict:
    started = time.perf_counter()
    verification = state.get("verification")
    claim_ids = state.get("claim_ids") or []
    chunk_ids = state.get("chunk_ids") or []
    wiki_pages = state.get("wiki_pages") or []
    if verification is None:
        effective_ids = claim_ids
    elif verification.verification_status == "partial":
        effective_ids = claim_ids
    else:
        effective_ids = verification.verified_claim_ids
    return {
        "claim_ids": effective_ids,
        "chunk_ids": chunk_ids,
        "wiki_pages": wiki_pages,
        "trace": [
            trace_step(
                "explain",
                summary=f"解释筛选 {len(effective_ids)} 条 Claim",
                detail={"claim_ids": effective_ids, "chunk_ids": chunk_ids},
                duration_ms=_node_duration_ms(started),
            )
        ],
    }


def synthesize_node(state: AskState, deps: Any) -> dict:
    started = time.perf_counter()
    settings = get_settings()
    claim_ids = state.get("claim_ids") or []
    chunk_ids = state.get("chunk_ids") or []
    wiki_pages = state.get("wiki_pages") or []
    question = state.get("normalized_question") or state["question"]
    if not settings.ask_synthesis:
        return {
            "synthesis_skipped_reason": "disabled",
            "trace": [
                trace_step(
                    "synthesize",
                    status="skipped",
                    summary="LLM 综合已关闭",
                    detail={"skipped_reason": "disabled"},
                    duration_ms=_node_duration_ms(started),
                )
            ],
        }
    if not claim_ids and not chunk_ids and not wiki_pages:
        return {
            "synthesis_skipped_reason": "no_context",
            "trace": [
                trace_step(
                    "synthesize",
                    status="skipped",
                    summary="无检索上下文，跳过综合",
                    detail={"skipped_reason": "no_context"},
                    duration_ms=_node_duration_ms(started),
                )
            ],
        }
    context = build_synthesis_context(
        question=question,
        claim_ids=claim_ids,
        chunk_ids=chunk_ids,
        wiki_pages=wiki_pages,
        hits=state.get("hits") or [],
        deps=deps,
        settings=settings,
    )
    result = synthesize_answer(context, deps.llm_client, settings)
    if result is None:
        return {
            "synthesis_skipped_reason": "failed",
            "trace": [
                trace_step(
                    "synthesize",
                    status="error",
                    summary="LLM 综合失败",
                    detail={"skipped_reason": "failed"},
                    duration_ms=_node_duration_ms(started),
                )
            ],
        }
    citations = result.get("citations", [])
    return {
        "synthesis_text": result["answer"],
        "synthesis_citations": citations,
        "synthesis_skipped_reason": None,
        "trace": [
            trace_step(
                "synthesize",
                summary=f"LLM 综合完成，{len(citations)} 条引用",
                detail={
                    "citation_count": len(citations),
                    "answer_chars": len(result["answer"]),
                    "citations": citations[:10],
                },
                duration_ms=_node_duration_ms(started),
            )
        ],
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
    duration_ms: int = 0,
) -> dict:
    answer = Answer(
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
    return {
        "answer": answer,
        "trace": [
            trace_step(
                "answer",
                summary=f"生成回答，置信度 {confidence:.0%}",
                detail={
                    "confidence": confidence,
                    "verification_status": verification_status,
                    "claim_count": len(claim_ids),
                    "chunk_count": len(chunk_ids),
                    "synthesis_used": synthesis_used,
                    "answer_chars": len(text),
                },
                duration_ms=duration_ms,
            )
        ],
    }


def answer_node(state: AskState, deps: Any) -> dict:
    started = time.perf_counter()
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

    def _answer(**kwargs: Any) -> dict:
        return _build_answer(duration_ms=_node_duration_ms(started), **kwargs)

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
        return _answer(
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

        return _answer(
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
        return _answer(
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
                    return _answer(
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
            return _answer(
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
            {"source_id": item["source_id"], "quote": item["quote"], "weight": item["weight"]} for item in bundle.items
        ]
        return _answer(
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
        return _answer(
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
    return _answer(
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
    started = time.perf_counter()
    session_id = state.get("session_id")
    answer = state.get("answer")
    if not session_id or answer is None:
        return {
            "trace": [
                trace_step(
                    "remember",
                    status="skipped",
                    summary="无会话或回答，跳过写入记忆",
                    detail={"session_id": session_id, "has_answer": answer is not None},
                    duration_ms=_node_duration_ms(started),
                )
            ]
        }

    episode = {
        "q": state.get("normalized_question") or state.get("question") or "",
        "a": getattr(answer, "text", "") or "",
    }
    memory_agent.remember(deps.memory, session_id, episode)
    return {
        "trace": [
            trace_step(
                "remember",
                summary="已写入会话记忆",
                detail={"session_id": session_id, "episode": episode},
                duration_ms=_node_duration_ms(started),
            )
        ]
    }
