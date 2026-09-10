from __future__ import annotations

import json
from typing import Any

from langsmith import traceable

from infra.settings import Settings
from knowledge.models import SourceChunk


def build_synthesis_context(
    *,
    question: str,
    claim_ids: list[str],
    chunk_ids: list[str],
    deps: Any,
    settings: Settings,
) -> dict[str, Any]:
    claims = []
    evidence = []
    for claim_id in claim_ids:
        claim = deps.knowledge.get_claim(claim_id)
        if claim is None:
            continue
        claims.append(
            {
                "id": claim.id,
                "subject": claim.subject,
                "predicate": claim.predicate,
                "object": claim.object,
                "confidence": claim.confidence,
            }
        )
    if claim_ids:
        bundle = deps.evidence.explain(claim_ids)
        for item in bundle.items:
            evidence.append(
                {
                    "source_id": item["source_id"],
                    "quote": item["quote"],
                    "claim_id": item.get("claim_id"),
                }
            )

    chunks = []
    for chunk_id in chunk_ids[: settings.ask_synthesis_max_chunks]:
        chunk = deps.knowledge.get_chunk(chunk_id)
        if chunk is None:
            continue
        chunks.append(_chunk_payload(chunk))

    return {"question": question, "claims": claims, "evidence": evidence, "chunks": chunks}


def _chunk_payload(chunk: SourceChunk) -> dict[str, Any]:
    excerpt = chunk.text[:500]
    return {
        "id": chunk.id,
        "source_id": chunk.source_id,
        "title": chunk.title,
        "summary": chunk.summary,
        "text_excerpt": excerpt,
        "quote": excerpt[:120],
    }


def _build_prompt(context: dict[str, Any]) -> str:
    return (
        "你是 AKOS 知识库问答助手。仅根据提供的 claims、evidence 与 chunks 回答，禁止编造。\n"
        "要求：\n"
        "1. 用中文自然语言回答用户问题\n"
        "2. 每个事实句末标注引用 [source_id:简短quote]\n"
        "3. 若 claims 冲突，说明冲突并列出双方\n"
        "4. 若信息不足，明确说「依据不足」\n"
        "只输出 JSON："
        '{"answer":"...", "citations":[{"source_id":"...","quote":"...","claim_id":null,"chunk_id":null}]}\n'
        f"上下文:\n{json.dumps(context, ensure_ascii=False)}"
    )


def _parse_json_response(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise ValueError("synthesis payload must be a JSON object")
    return payload


def _context_texts_for_source(context: dict[str, Any], source_id: str) -> list[str]:
    texts: list[str] = []
    for item in context.get("evidence", []):
        if item.get("source_id") == source_id:
            quote = item.get("quote")
            if isinstance(quote, str) and quote:
                texts.append(quote)
    for item in context.get("chunks", []):
        if item.get("source_id") != source_id:
            continue
        for field in ("text_excerpt", "summary", "quote", "title"):
            value = item.get(field)
            if isinstance(value, str) and value:
                texts.append(value)
    return texts


def _quote_allowed(quote: str, context: dict[str, Any], source_id: str | None = None) -> bool:
    if not quote:
        return False
    candidates: list[str] = []
    if source_id:
        candidates.extend(_context_texts_for_source(context, source_id))
    else:
        for item in context.get("evidence", []):
            value = item.get("quote")
            if isinstance(value, str):
                candidates.append(value)
        for item in context.get("chunks", []):
            for field in ("text_excerpt", "summary", "quote", "title"):
                value = item.get(field)
                if isinstance(value, str):
                    candidates.append(value)
    for candidate in candidates:
        if quote in candidate or candidate in quote:
            return True
    return False


def _answer_grounded_in_context(answer: str, context: dict[str, Any]) -> bool:
    for item in context.get("evidence", []):
        quote = item.get("quote")
        if isinstance(quote, str) and len(quote) >= 6 and quote in answer:
            return True
    for item in context.get("chunks", []):
        for field in ("text_excerpt", "summary"):
            text = item.get(field)
            if isinstance(text, str) and len(text) >= 12 and text[: min(40, len(text))] in answer:
                return True
    return False


def sanitize_synthesis_payload(context: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any] | None:
    """Keep LLM answer; drop invalid citations instead of rejecting the whole synthesis."""
    answer = payload.get("answer")
    if not isinstance(answer, str) or not answer.strip():
        return None

    raw_citations = payload.get("citations")
    citations: list[dict[str, Any]] = []
    if isinstance(raw_citations, list):
        for citation in raw_citations:
            if not isinstance(citation, dict):
                continue
            source_id = citation.get("source_id")
            quote = citation.get("quote")
            if not isinstance(source_id, str) or not isinstance(quote, str):
                continue
            if _quote_allowed(quote, context, source_id):
                citations.append(citation)

    if citations or _answer_grounded_in_context(answer, context):
        return {"answer": answer.strip(), "citations": citations}
    return None


def validate_synthesis_result(context: dict[str, Any], payload: dict[str, Any]) -> bool:
    return sanitize_synthesis_payload(context, payload) is not None


@traceable(name="akos.synthesize_answer", run_type="chain")
def synthesize_answer(context: dict[str, Any], llm_client, settings: Settings) -> dict[str, Any] | None:
    if not settings.ask_synthesis or llm_client is None or not llm_client.is_configured:
        return None
    if not context.get("claims") and not context.get("chunks"):
        return None
    try:
        raw = llm_client.chat_completions(
            [{"role": "user", "content": _build_prompt(context)}],
            temperature=settings.ask_synthesis_temperature,
        )
        payload = _parse_json_response(raw)
    except Exception:
        return None
    return sanitize_synthesis_payload(context, payload)
