from __future__ import annotations

from typing import Any

_TRACE_FIELDS = {"node", "status", "summary", "duration_ms", "detail"}


def serialize_hit_for_trace(hit: Any, knowledge: Any | None = None, *, limit_text: int = 160) -> dict[str, Any]:
    hit_type = getattr(hit, "hit_type", None) or ("claim" if getattr(hit, "claim_id", None) else "chunk")
    item: dict[str, Any] = {
        "hit_type": hit_type,
        "score": round(float(getattr(hit, "score", 0.0)), 4),
    }
    snippet = getattr(hit, "snippet", None)
    if isinstance(snippet, str) and snippet.strip():
        item["snippet"] = snippet[:limit_text]
    claim_id = getattr(hit, "claim_id", None)
    if claim_id:
        item["claim_id"] = claim_id
    chunk_id = getattr(hit, "chunk_id", None)
    if chunk_id:
        item["chunk_id"] = chunk_id
    source_id = getattr(hit, "source_id", None)
    if source_id:
        item["source_id"] = source_id
    ref_id = getattr(hit, "ref_id", None)
    if ref_id:
        item["ref_id"] = ref_id
    path = getattr(hit, "path", None)
    if path:
        item["path"] = path
    title = getattr(hit, "title", None)
    if title:
        item["title"] = title
    if knowledge is not None and chunk_id:
        chunk = knowledge.get_chunk(chunk_id)
        if chunk is not None:
            item["chunk_index"] = chunk.chunk_index
            if chunk.title:
                item["title"] = chunk.title
    return item


def serialize_hits_for_trace(hits: list[Any], knowledge: Any | None = None, *, limit: int = 10) -> list[dict[str, Any]]:
    return [serialize_hit_for_trace(hit, knowledge) for hit in hits[:limit]]


def serialize_chunk_for_trace(knowledge: Any, chunk_id: str, *, limit_text: int = 160) -> dict[str, Any]:
    chunk = knowledge.get_chunk(chunk_id)
    if chunk is None:
        return {"chunk_id": chunk_id}
    excerpt = chunk.summary or chunk.text
    return {
        "chunk_id": chunk.id,
        "source_id": chunk.source_id,
        "chunk_index": chunk.chunk_index,
        "title": chunk.title,
        "excerpt": excerpt[:limit_text],
        "status": chunk.status,
    }


def serialize_chunks_for_trace(knowledge: Any, chunk_ids: list[str], *, limit: int = 10) -> list[dict[str, Any]]:
    return [serialize_chunk_for_trace(knowledge, chunk_id) for chunk_id in chunk_ids[:limit]]


def trace_step(
    node: str,
    *,
    status: str = "ok",
    summary: str = "",
    detail: dict[str, Any] | None = None,
    duration_ms: int | None = None,
) -> dict[str, Any]:
    step: dict[str, Any] = {"node": node, "status": status, "summary": summary}
    if detail is not None:
        step["detail"] = detail
    if duration_ms is not None:
        step["duration_ms"] = duration_ms
    return step


def _default_summary(node: str, detail: dict[str, Any] | None) -> str:
    if not detail:
        return node
    if node == "retrieve":
        return (
            f"命中 {detail.get('hit_count', 0)} 条"
            f"（Claim {detail.get('claim_hits', 0)}"
            f" / Wiki {detail.get('wiki_hits', 0)}"
            f" / Chunk {detail.get('chunk_hits', 0)}）"
        )
    if node == "verify":
        return (
            f"核验 {detail.get('verification_status', 'verified')}，"
            f"{len(detail.get('claim_ids') or [])} 条 Claim / "
            f"{len(detail.get('wiki_pages') or [])} 页 Wiki / "
            f"{len(detail.get('chunk_ids') or [])} 条 Chunk"
        )
    if node == "route_mode":
        return f"检索模式 {detail.get('retrieval_mode', 'hybrid')}"
    if node == "synthesize":
        if detail.get("skipped_reason"):
            return f"跳过综合：{detail['skipped_reason']}"
        return f"LLM 综合完成，{detail.get('citation_count', 0)} 条引用"
    if node == "answer":
        return f"生成回答，置信度 {detail.get('confidence', 0):.0%}"
    return node


def normalize_agent_trace(steps: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for step in steps or []:
        if not isinstance(step, dict):
            continue
        node = str(step.get("node") or "unknown")
        detail = step.get("detail")
        if not isinstance(detail, dict):
            extra = {key: value for key, value in step.items() if key not in _TRACE_FIELDS}
            detail = extra or None
        status = step.get("status", "ok")
        if status not in {"ok", "error", "skipped"}:
            status = "ok"
        summary = step.get("summary")
        if not isinstance(summary, str) or not summary.strip():
            summary = _default_summary(node, detail if isinstance(detail, dict) else None)
        payload: dict[str, Any] = {"node": node, "status": status, "summary": summary}
        if isinstance(detail, dict) and detail:
            payload["detail"] = detail
        duration_ms = step.get("duration_ms")
        if isinstance(duration_ms, int):
            payload["duration_ms"] = duration_ms
        normalized.append(payload)
    return normalized
