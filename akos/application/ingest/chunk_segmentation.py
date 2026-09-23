from __future__ import annotations

import hashlib
import json
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from akos.application.ingest.chunker import DocumentChunkDraft, estimate_token_count, validate_chunk_coverage
from akos.adapters.llm.client import LlmCallError
from infra.settings import Settings
from akos.domain.models.knowledge import SourceChunk

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StructuralSpan:
    index: int
    title: str | None
    text: str
    start: int
    end: int
    section_path: list[str]


@dataclass(frozen=True)
class SegmentSection:
    title: str
    summary: str
    topics: list[str]
    span_indexes: list[int]


def spans_from_chunks(chunks: list[SourceChunk]) -> list[StructuralSpan]:
    ordered = sorted(chunks, key=lambda item: item.chunk_index)
    return [
        StructuralSpan(
            index=item.chunk_index,
            title=item.title,
            text=item.text,
            start=item.start,
            end=item.end,
            section_path=list(item.section_path),
        )
        for item in ordered
    ]


def _build_segmentation_prompt(spans: list[StructuralSpan], *, max_sections: int, min_tokens: int) -> str:
    payload = [
        {
            "index": span.index,
            "title": span.title,
            "token_count": estimate_token_count(span.text),
            "section_path": span.section_path,
            "excerpt": span.text[:240],
        }
        for span in spans
    ]
    return (
        "# 角色\n"
        "你是文档章节规划助手，负责把结构切分后的 span 整理成类似 Wiki 章节的 chunk 规划。\n"
        "\n"
        "# 目标\n"
        "合并语义相关的相邻 span，形成可读、可检索的章节边界；不改写原文，只规划合并范围。\n"
        "\n"
        "# 规则\n"
        f"- sections 数量不超过 {max_sections}\n"
        "- 每个 span index 必须出现且仅出现一次\n"
        "- 同一 section 的 span_indexes 必须连续递增\n"
        "- 优先按 ## 级主题合并，避免 1-token 标题块单独成章\n"
        f"- 每个 section 合并后的正文至少约 {min_tokens} tokens，过短块必须与相邻 span 合并\n"
        "- 不要改写原文内容，只输出合并边界与章节元数据\n"
        "\n"
        "# 输出\n"
        "只输出一个 JSON 对象，不要 Markdown 代码围栏，不要其他说明。\n"
        '格式：{"sections":[{"title":"...","summary":"...","topics":["..."],"span_indexes":[0,1]}]}\n'
        "\n"
        "# 参考\n"
        f"spans: {json.dumps(payload, ensure_ascii=False)}\n"
    )


def parse_segmentation_plan(raw: str, *, span_count: int) -> list[SegmentSection] | None:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    sections_raw = payload.get("sections")
    if not isinstance(sections_raw, list) or not sections_raw:
        return None

    sections: list[SegmentSection] = []
    seen: set[int] = set()
    for item in sections_raw:
        if not isinstance(item, dict):
            return None
        title = item.get("title")
        summary = item.get("summary")
        topics = item.get("topics")
        span_indexes = item.get("span_indexes")
        if not isinstance(title, str) or not title.strip():
            return None
        if not isinstance(summary, str) or not summary.strip():
            return None
        if not isinstance(topics, list):
            return None
        if not isinstance(span_indexes, list) or not span_indexes:
            return None
        normalized_indexes: list[int] = []
        for value in span_indexes:
            if not isinstance(value, int) or value < 0 or value >= span_count:
                return None
            if value in seen:
                return None
            normalized_indexes.append(value)
            seen.add(value)
        normalized_indexes.sort()
        for left, right in zip(normalized_indexes, normalized_indexes[1:]):
            if right != left + 1:
                return None
        sections.append(
            SegmentSection(
                title=title.strip(),
                summary=summary.strip(),
                topics=[str(topic).strip() for topic in topics if str(topic).strip()],
                span_indexes=normalized_indexes,
            )
        )

    if seen != set(range(span_count)):
        return None
    return sections


def merge_small_spans(text: str, spans: list[StructuralSpan], *, min_tokens: int = 50) -> list[StructuralSpan]:
    """合并相邻结构 span，使每组至少 min_tokens（末尾不足一组时除外）。"""
    if not spans or min_tokens <= 0:
        return spans

    def _group_tokens(group: list[StructuralSpan]) -> int:
        return estimate_token_count(text[group[0].start : group[-1].end])

    groups: list[list[StructuralSpan]] = [[spans[0]]]
    for span in spans[1:]:
        if _group_tokens(groups[-1]) < min_tokens:
            groups[-1].append(span)
        else:
            groups.append([span])

    # Collapse leftover undersized groups into neighbors (prefer forward merge).
    index = 0
    while index < len(groups) - 1:
        if _group_tokens(groups[index]) < min_tokens:
            groups[index].extend(groups.pop(index + 1))
            continue
        index += 1
    if len(groups) > 1 and _group_tokens(groups[-1]) < min_tokens:
        groups[-2].extend(groups.pop())

    merged: list[StructuralSpan] = []
    for index, group in enumerate(groups):
        first = group[0]
        last = group[-1]
        title = first.title or (first.section_path[-1] if first.section_path else f"段落 {index + 1}")
        merged.append(
            StructuralSpan(
                index=index,
                title=title,
                text=text[first.start : last.end],
                start=first.start,
                end=last.end,
                section_path=list(first.section_path),
            )
        )
    return merged


def spans_cover_same_ranges(left: list[StructuralSpan], right: list[StructuralSpan]) -> bool:
    if len(left) != len(right):
        return False
    return all(a.start == b.start and a.end == b.end for a, b in zip(left, right))


def build_compact_source_chunks(source_id: str, text: str, spans: list[StructuralSpan]) -> list[SourceChunk]:
    now = datetime.now(timezone.utc)
    chunks: list[SourceChunk] = []
    for index, span in enumerate(spans):
        span_text = text[span.start : span.end]
        chunks.append(
            SourceChunk(
                id=str(uuid.uuid4()),
                source_id=source_id,
                chunk_index=index,
                title=span.title,
                summary=None,
                text=span_text,
                start=span.start,
                end=span.end,
                section_path=list(span.section_path),
                topics=[],
                token_count=estimate_token_count(span_text),
                status="active",
                content_hash=_content_hash(span_text),
                created_at=now,
            )
        )
    validate_chunk_coverage(text, [DocumentChunkDraft(index, span.title, span.text, span.start, span.end, span.section_path) for index, span in enumerate(spans)])
    return chunks


def compact_small_chunks(
    source_id: str,
    text: str,
    chunks: list[SourceChunk],
    *,
    min_tokens: int,
) -> tuple[list[SourceChunk], bool]:
    spans = merge_small_spans(text, spans_from_chunks(chunks), min_tokens=min_tokens)
    original_spans = spans_from_chunks(chunks)
    if spans_cover_same_ranges(original_spans, spans):
        return chunks, False
    return build_compact_source_chunks(source_id, text, spans), True


def apply_segmentation_plan(
    text: str,
    spans: list[StructuralSpan],
    sections: list[SegmentSection],
) -> list[DocumentChunkDraft]:
    span_by_index = {span.index: span for span in spans}
    drafts: list[DocumentChunkDraft] = []
    for chunk_index, section in enumerate(sections):
        first = span_by_index[section.span_indexes[0]]
        last = span_by_index[section.span_indexes[-1]]
        merged_text = text[first.start : last.end]
        drafts.append(
            DocumentChunkDraft(
                chunk_index=chunk_index,
                title=section.title,
                text=merged_text,
                start=first.start,
                end=last.end,
                section_path=list(first.section_path),
            )
        )
    validate_chunk_coverage(text, drafts)
    return drafts


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def build_segmented_source_chunks(
    source_id: str,
    text: str,
    drafts: list[DocumentChunkDraft],
    sections: list[SegmentSection],
) -> list[SourceChunk]:
    now = datetime.now(timezone.utc)
    chunks: list[SourceChunk] = []
    for draft, section in zip(drafts, sections):
        chunks.append(
            SourceChunk(
                id=str(uuid.uuid4()),
                source_id=source_id,
                chunk_index=draft.chunk_index,
                title=section.title,
                summary=section.summary,
                text=draft.text,
                start=draft.start,
                end=draft.end,
                section_path=list(draft.section_path),
                topics=list(section.topics),
                token_count=estimate_token_count(draft.text),
                status="active",
                content_hash=_content_hash(draft.text),
                created_at=now,
            )
        )
    return chunks


def request_segmentation_plan(client: Any, spans: list[StructuralSpan], settings: Settings) -> list[SegmentSection] | None:
    if not spans:
        return None
    prompt = _build_segmentation_prompt(
        spans,
        max_sections=settings.chunk_llm_segment_max_sections,
        min_tokens=settings.chunk_min_tokens,
    )
    last_error: Exception | None = None
    for attempt in range(2):
        try:
            raw = client.chat_completions([{"role": "user", "content": prompt}], temperature=0.0)
            sections = parse_segmentation_plan(raw, span_count=len(spans))
            if sections is not None:
                return sections
            last_error = LlmCallError("章节规划 LLM 返回无法解析的 JSON")
        except Exception as exc:
            last_error = exc
            if attempt == 0:
                logger.warning("章节规划 LLM 调用失败，重试一次: %s", exc)
                continue
            logger.exception("章节规划 LLM 调用失败")
            raise
    raise LlmCallError(f"章节规划 LLM 未返回有效结果: {last_error}") from last_error
