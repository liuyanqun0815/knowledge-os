from __future__ import annotations

import json
import logging
from dataclasses import replace
from typing import Any

from langsmith import traceable

from infra.settings import Settings

logger = logging.getLogger(__name__)


def _build_prompt(chunk_index: int, text: str) -> str:
    return (
        "你是文档标注助手。根据给定 chunk 生成标题、摘要和主题词。\n"
        "只输出 JSON 对象，字段：chunk_index, title, summary, topics。\n"
        f"chunk_index 必须为 {chunk_index}。\n"
        "不要修改原文，不要编造 chunk 中不存在的信息。\n"
        f"chunk:\n{text[:2000]}"
    )


def _parse_enrichment(raw: str, chunk_index: int) -> dict[str, Any] | None:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    if payload.get("chunk_index") != chunk_index:
        return None
    title = payload.get("title")
    summary = payload.get("summary")
    topics = payload.get("topics")
    if not isinstance(summary, str) or not summary.strip():
        return None
    if title is not None and not isinstance(title, str):
        return None
    if topics is not None and not isinstance(topics, list):
        return None
    return {
        "title": title.strip() if isinstance(title, str) and title.strip() else None,
        "summary": summary.strip(),
        "topics": [str(item).strip() for item in topics if str(item).strip()] if isinstance(topics, list) else [],
    }


def _maybe_compile_wiki(*, kb_id: str, source_id: str, deps: Any, settings: Settings) -> None:
    if not getattr(settings, "wiki_compile", False):
        return
    data_root = getattr(settings, "data_root", None) or getattr(deps, "data_root", None)
    if not data_root:
        return
    from wiki.compile import compile_topics_for_source

    compile_topics_for_source(
        deps.knowledge,
        kb_id,
        source_id,
        data_root,
        settings,
        graph=getattr(deps, "graph", None),
    )


@traceable(name="akos.enrich_chunks", run_type="chain")
def enrich_chunks(*, kb_id: str, source_id: str, deps: Any, settings: Settings) -> None:
    client = getattr(deps, "llm_client", None)
    if not settings.chunk_llm_enrich or client is None or not client.is_configured:
        return
    if getattr(deps, "chunk_retrieval", None) is None:
        return

    chunks = deps.knowledge.list_chunks(source_id, status="active")
    if not chunks:
        return

    for chunk in chunks:
        enriched = None
        for attempt in range(2):
            try:
                raw = client.chat_completions(
                    [{"role": "user", "content": _build_prompt(chunk.chunk_index, chunk.text)}],
                    temperature=0.0,
                )
                enriched = _parse_enrichment(raw, chunk.chunk_index)
                if enriched is not None:
                    break
            except Exception:
                if attempt == 1:
                    logger.exception(
                        "Chunk enrichment failed for source %s chunk %s in kb %s",
                        source_id,
                        chunk.id,
                        kb_id,
                    )
        if enriched is None:
            continue
        updated = deps.knowledge.update_chunk(
            replace(
                chunk,
                title=enriched["title"] or chunk.title,
                summary=enriched["summary"],
                topics=enriched["topics"] or chunk.topics,
            )
        )
        deps.chunk_retrieval.index_chunks([updated])

    if settings.topic_cluster:
        graph = getattr(deps, "graph", None)
        if graph is not None:
            from knowledge.topic_service import rebuild_topic_clusters

            rebuild_topic_clusters(deps.knowledge, graph, kb_id, settings)

    _maybe_compile_wiki(kb_id=kb_id, source_id=source_id, deps=deps, settings=settings)
    logger.info("Chunk enrichment finished for source %s in kb %s", source_id, kb_id)
