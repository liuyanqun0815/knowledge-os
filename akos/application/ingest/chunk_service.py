from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime, timezone

from akos.application.ingest.chunker import chunk_document, estimate_token_count
from akos.domain.ports.compiler import ChunkIndexReport
from infra.settings import Settings
from akos.domain.models.knowledge import SourceChunk
from akos.domain.ports.knowledge import KnowledgePort

logger = logging.getLogger("akos.ingest.flow")


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _fold_overflow_chunks(chunks: list[SourceChunk], text: str, *, max_chunks: int) -> tuple[list[SourceChunk], bool]:
    if len(chunks) <= max_chunks:
        return chunks, False
    kept = chunks[: max_chunks - 1]
    overflow = chunks[max_chunks - 1 :]
    first = overflow[0]
    last = overflow[-1]
    merged_text = text[first.start : last.end]
    folded = SourceChunk(
        id=str(uuid.uuid4()),
        source_id=first.source_id,
        chunk_index=max_chunks - 1,
        title=first.title,
        summary=None,
        text=merged_text,
        start=first.start,
        end=last.end,
        section_path=list(first.section_path),
        topics=[],
        token_count=estimate_token_count(merged_text),
        status="active",
        content_hash=_content_hash(merged_text),
        created_at=first.created_at,
    )
    return kept + [folded], True


def build_source_chunks(source_id: str, text: str, settings: Settings) -> tuple[list[SourceChunk], bool]:
    # 先结构切分（上限放宽，避免空行碎块被 max_chunks 压成一条大尾），再 compact，最后 fold。
    structural_cap = max(settings.chunk_max_per_doc * 20, 500)
    result = chunk_document(
        text,
        settings.chunk_max_chars,
        structural_cap,
        mode=settings.chunk_mode,
        heading_level=settings.chunk_heading_level,
    )
    now = datetime.now(timezone.utc)
    chunks: list[SourceChunk] = []
    for draft in result.chunks:
        chunks.append(
            SourceChunk(
                id=str(uuid.uuid4()),
                source_id=source_id,
                chunk_index=draft.chunk_index,
                title=draft.title,
                summary=None,
                text=draft.text,
                start=draft.start,
                end=draft.end,
                section_path=list(draft.section_path),
                topics=[],
                token_count=estimate_token_count(draft.text),
                status="active",
                content_hash=_content_hash(draft.text),
                created_at=now,
            )
        )
    # compile 前合并过短的空行/标题碎块。
    before_compact = len(chunks)
    if settings.chunk_min_tokens > 0 and len(chunks) > 1:
        from akos.application.ingest.chunk_segmentation import compact_small_chunks

        chunks, _changed = compact_small_chunks(
            source_id,
            text,
            chunks,
            min_tokens=settings.chunk_min_tokens,
        )
    after_compact = len(chunks)
    chunks, folded = _fold_overflow_chunks(chunks, text, max_chunks=settings.chunk_max_per_doc)
    logger.debug(
        "结构切分 source=%s 结构=%s compact后=%s 最终=%s truncated=%s folded=%s",
        source_id,
        before_compact,
        after_compact,
        len(chunks),
        result.truncated,
        folded,
    )
    return chunks, bool(result.truncated or folded)


def index_source_chunks(
    knowledge: KnowledgePort,
    chunk_retrieval,
    source_id: str,
    settings: Settings,
) -> ChunkIndexReport:
    text = knowledge.get_source_text(source_id)
    if text is None:
        return ChunkIndexReport(
            source_id=source_id,
            chunks_created=0,
            truncated=False,
            errors=["source text not found"],
        )

    try:
        chunks, truncated = build_source_chunks(source_id, text, settings)
        knowledge.save_chunks(source_id, chunks)
        if settings.purge_stale_chunks:
            knowledge.purge_stale_chunks(source_id)
        if chunk_retrieval is not None:
            chunk_retrieval.remove_source(source_id)
            chunk_retrieval.index_chunks(chunks)
        return ChunkIndexReport(
            source_id=source_id,
            chunks_created=len(chunks),
            truncated=truncated,
            errors=[],
        )
    except Exception as exc:
        return ChunkIndexReport(
            source_id=source_id,
            chunks_created=0,
            truncated=False,
            errors=[str(exc)],
        )
