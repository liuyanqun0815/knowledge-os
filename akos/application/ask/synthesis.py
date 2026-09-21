from __future__ import annotations

import json
import re
from typing import Any

from langsmith import traceable

from infra.settings import Settings
from akos.domain.models.knowledge import SourceChunk


def build_synthesis_context(
    *,
    question: str,
    claim_ids: list[str],
    chunk_ids: list[str],
    deps: Any,
    settings: Settings,
    wiki_pages: list[dict[str, Any]] | None = None,
    hits: list[Any] | None = None,
) -> dict[str, Any]:
    """Pack LLM context from verified claims + rerank hits (claim-first).

    When ``hits`` is provided, non-claim records follow that order (no
    ``ask_synthesis_max_chunks`` cap); each chunk/wiki body is truncated to
    ``ask_synthesis_content_max_chars``.
    """
    max_chars = max(int(settings.ask_synthesis_content_max_chars), 1)
    allowed_claims = set(claim_ids)

    claims = []
    evidence = []
    chunks: list[dict[str, Any]] = []
    pages: list[dict[str, Any]] = []
    seen_chunks: set[str] = set()
    seen_wiki: set[str] = set()

    if hits:
        for hit in hits:
            hit_type = getattr(hit, "hit_type", None) or "claim"
            if hit_type == "chunk":
                chunk_id = getattr(hit, "chunk_id", None)
                if not chunk_id or chunk_id in seen_chunks:
                    continue
                chunk = deps.knowledge.get_chunk(chunk_id)
                if chunk is None:
                    continue
                seen_chunks.add(chunk_id)
                chunks.append(_chunk_payload(chunk, max_chars=max_chars))
            elif hit_type == "wiki":
                key = getattr(hit, "ref_id", None) or getattr(hit, "path", None) or getattr(hit, "snippet", None) or ""
                if not key or key in seen_wiki:
                    continue
                seen_wiki.add(key)
                pages.append(_wiki_payload(hit, max_chars=max_chars))
            else:
                claim_id = getattr(hit, "claim_id", None)
                if not claim_id or claim_id not in allowed_claims:
                    continue
                if any(item["id"] == claim_id for item in claims):
                    continue
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
        # Include verified claims missing from hits (e.g. explain-only ids).
        for claim_id in claim_ids:
            if any(item["id"] == claim_id for item in claims):
                continue
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
    else:
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
        for chunk_id in chunk_ids[: settings.ask_synthesis_max_chunks]:
            chunk = deps.knowledge.get_chunk(chunk_id)
            if chunk is None:
                continue
            chunks.append(_chunk_payload(chunk, max_chars=max_chars))
        for page in list(wiki_pages or [])[: settings.ask_synthesis_max_chunks]:
            pages.append(_truncate_wiki_page(page, max_chars=max_chars))

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

    return {
        "question": question,
        "claims": claims,
        "evidence": evidence,
        "chunks": chunks,
        "wiki_pages": pages,
    }


def _chunk_payload(chunk: SourceChunk, *, max_chars: int = 800) -> dict[str, Any]:
    excerpt = (chunk.text or "")[:max_chars]
    return {
        "id": chunk.id,
        "source_id": chunk.source_id,
        "title": chunk.title,
        "summary": chunk.summary,
        "text_excerpt": excerpt,
        "quote": excerpt[:120],
    }


def _truncate_text(value: str | None, max_chars: int) -> str:
    text = value or ""
    return text[:max_chars]


def _wiki_payload(hit: Any, *, max_chars: int) -> dict[str, Any]:
    content = _truncate_text(getattr(hit, "content", None) or getattr(hit, "snippet", None), max_chars)
    excerpt = _truncate_text(getattr(hit, "snippet", None) or content, max_chars)
    return {
        "title": getattr(hit, "title", None) or getattr(hit, "ref_id", None) or "",
        "excerpt": excerpt,
        "content": content,
        "path": getattr(hit, "path", None) or "",
        "links": [],
        "ref_id": getattr(hit, "ref_id", None),
    }


def _truncate_wiki_page(page: dict[str, Any], *, max_chars: int) -> dict[str, Any]:
    out = dict(page)
    if isinstance(out.get("content"), str):
        out["content"] = out["content"][:max_chars]
    if isinstance(out.get("excerpt"), str):
        out["excerpt"] = out["excerpt"][:max_chars]
    return out


def _build_prompt(context: dict[str, Any]) -> str:
    question = context.get("question", "")
    if not isinstance(question, str):
        question = str(question)
    wiki_pages = context.get("wiki_pages") or []
    knowledge_context = {
        "claims": context.get("claims", []),
        "evidence": context.get("evidence", []),
        "chunks": context.get("chunks", []),
        "wiki_pages": wiki_pages,
    }
    return (
        "# 角色\n"
        "你是 AKOS 知识库问答助手。\n"
        "\n"
        "# 目标\n"
        "仅根据下方「参考」中的 claims、evidence、chunks、wiki_pages 作答；"
        "禁止编造、禁止引入参考以外的内容。\n"
        "\n"
        "# 规则\n"
        "## 回答原则\n"
        "1. 语言：使用简洁、专业、面向业务用户的中文自然语言\n"
        "2. 聚焦：直接回应「用户问题」，优先使用与问题最相关的 claims 与 chunks；"
        "Wiki 主题页仅作结构与综述参考，数字与规则仍以 Claim/原文为准\n"
        "3. 结构：先给出结论，再补充适用条件、例外情形或操作要点；必要时使用短列表\n"
        "4. 数值与规则：涉及天数、金额、比例等须与 Claim/原文（claims、evidence、chunks）一致，"
        "不可四舍五入或自行推断；数字与规则以 Claim/原文为准\n"
        "5. 冲突：若 claims 对同一问题给出不同结论，说明存在冲突并分别陈述双方依据\n"
        "6. 不足：若参考知识无法支撑可靠结论，answer 仅输出「依据不足」，citations 输出空数组 []\n"
        "7. 引用分工：answer 正文必须是纯文本结论，不得出现任何引用标注"
        "（禁止 [source_id:...]、[1]、脚注、括号来源等）；所有可追溯引用仅写入 citations 数组\n"
        "\n"
        "## citations 填写规则\n"
        "- 每条 citation 必须包含 source_id 与 quote（quote 须为参考知识原文的可核对摘录，可短摘）\n"
        "- 依据来自 claim 时填写 claim_id，来自 chunk 时填写 chunk_id；"
        "引用 wiki 时 source_id 填 path 或 title，claim_id/chunk_id 填 null\n"
        "- 引用类型可为 claim | chunk | wiki\n"
        "- 仅收录 answer 中实际用到的依据，不要堆砌无关 citation\n"
        "- 同一 source 的多条依据可拆成多条 citation\n"
        "\n"
        "# 输出\n"
        "只输出一个 JSON 对象，不要 markdown 代码块，不要前后说明文字：\n"
        '{"answer":"...","citations":[{"source_id":"...","quote":"...","claim_id":null,"chunk_id":null}]}\n'
        "\n"
        "# 参考\n"
        f"## 用户问题\n{question.strip()}\n\n"
        f"## Wiki 主题页\n{json.dumps(wiki_pages, ensure_ascii=False)}\n\n"
        f"## 参考知识\n{json.dumps(knowledge_context, ensure_ascii=False)}\n"
    )


_INLINE_CITATION_PATTERN = re.compile(r"\[[^\[\]:]+:[^\[\]]+\]")
_FOOTNOTE_CITATION_PATTERN = re.compile(r"\[\d+\]")


def _strip_inline_citations(answer: str) -> str:
    cleaned = _INLINE_CITATION_PATTERN.sub("", answer)
    cleaned = _FOOTNOTE_CITATION_PATTERN.sub("", cleaned)
    cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
    cleaned = re.sub(r" {2,}", " ", cleaned)
    cleaned = re.sub(r"\s+([。；，、！？])", r"\1", cleaned)
    return cleaned.strip()


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
    for item in context.get("wiki_pages", []):
        path = item.get("path")
        title = item.get("title")
        if source_id not in {path, title, item.get("ref_id")}:
            continue
        for field in ("content", "excerpt", "title", "path"):
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
        for item in context.get("wiki_pages", []):
            for field in ("content", "excerpt", "title"):
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
    for item in context.get("wiki_pages", []):
        for field in ("content", "excerpt"):
            text = item.get(field)
            if isinstance(text, str) and len(text) >= 12 and text[: min(40, len(text))] in answer:
                return True
    return False


def sanitize_synthesis_payload(context: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any] | None:
    """Keep LLM answer; drop invalid citations instead of rejecting the whole synthesis."""
    answer = payload.get("answer")
    if not isinstance(answer, str) or not answer.strip():
        return None
    answer = _strip_inline_citations(answer)
    if not answer:
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
        return {"answer": answer, "citations": citations}
    return None


def validate_synthesis_result(context: dict[str, Any], payload: dict[str, Any]) -> bool:
    return sanitize_synthesis_payload(context, payload) is not None


@traceable(name="akos.synthesize_answer", run_type="chain")
def synthesize_answer(context: dict[str, Any], llm_client, settings: Settings) -> dict[str, Any] | None:
    if not settings.ask_synthesis or llm_client is None or not llm_client.is_configured:
        return None
    if not context.get("claims") and not context.get("chunks") and not context.get("wiki_pages"):
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
