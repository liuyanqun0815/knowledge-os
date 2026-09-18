from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone

from akos.application.ingest.chunker import chunk_document, estimate_token_count
from akos.domain.ports.compiler import ChunkIndexReport
from infra.settings import Settings
from akos.domain.models.knowledge import SourceChunk
from akos.domain.ports.knowledge import KnowledgePort


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def build_source_chunks(source_id: str, text: str, settings: Settings) -> tuple[list[SourceChunk], bool]:
    result = chunk_document(
        text,
        settings.chunk_max_chars,
        settings.chunk_max_per_doc,
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
    return chunks, result.truncated


def index_source_chunks(
    knowledge: KnowledgePort,
    chunk_retrieval,
    source_id: str,
    settings: Settings,
) -> ChunkIndexReport:
    if not settings.chunk_index:
        return ChunkIndexReport(source_id=source_id, chunks_created=0, truncated=False, errors=[])

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
