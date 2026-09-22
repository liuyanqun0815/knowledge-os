from __future__ import annotations

import json
import logging
from typing import Any

from langsmith import traceable

from akos.application.ingest.chunk_segmentation import (
    apply_segmentation_plan,
    build_segmented_source_chunks,
    request_segmentation_plan,
    spans_from_chunks,
)
from infra.settings import Settings

logger = logging.getLogger(__name__)


def _build_prompt(chunk_index: int, text: str) -> str:
    return (
        "# 角色\n"
        "你是文档标注助手，为已切分的 chunk 生成检索友好的元数据。\n"
        "\n"
        "# 目标\n"
        "根据给定 chunk 生成 title、summary、topics，便于浏览与主题聚类。\n"
        "\n"
        "# 规则\n"
        f"- chunk_index 必须为 {chunk_index}\n"
        "- 不要修改原文，不要编造 chunk 中不存在的信息\n"
        "- title 简洁；summary 概括要点；topics 为短词列表\n"
        "\n"
        "# 输出\n"
        "只输出一个 JSON 对象，不要 Markdown 代码围栏，不要其他说明。\n"
        f'格式：{{"chunk_index":{chunk_index},"title":"...","summary":"...","topics":["..."]}}\n'
        "\n"
        "# 参考\n"
        f"chunk:\n{text[:2000]}\n"
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


def _rebuild_topic_clusters(deps: Any, kb_id: str, settings: Settings) -> None:
    if not settings.topic_cluster:
        return
    graph = getattr(deps, "graph", None)
    if graph is None:
        return
    from akos.application.topics.service import rebuild_topic_clusters

    rebuild_topic_clusters(deps.knowledge, graph, kb_id, settings)


def _maybe_compile_wiki(*, kb_id: str, source_id: str, deps: Any, settings: Settings) -> None:
    if not getattr(settings, "wiki_compile", False):
        return
    data_root = getattr(settings, "data_root", None) or getattr(deps, "data_root", None)
    if not data_root:
        return
    from akos.application.wiki.compile import compile_topics_for_source
    from akos.application.wiki.paths import compile_wiki_root

    compile_topics_for_source(
        deps.knowledge,
        kb_id,
        source_id,
        data_root,
        settings,
        graph=getattr(deps, "graph", None),
        llm_client=getattr(deps, "llm_client", None),
    )
    wiki_retrieval = getattr(deps, "wiki_retrieval", None)
    if wiki_retrieval is not None:
        wiki_retrieval.index_wiki_root(compile_wiki_root(data_root, kb_id))


def _persist_chunks(deps: Any, source_id: str, chunks: list, settings: Settings) -> None:
    deps.knowledge.save_chunks(source_id, chunks)
    if settings.purge_stale_chunks:
        deps.knowledge.purge_stale_chunks(source_id)
    chunk_retrieval = getattr(deps, "chunk_retrieval", None)
    if chunk_retrieval is None:
        return
    chunk_retrieval.remove_source(source_id)
    chunk_retrieval.index_chunks(chunks)


def plan_chunks_for_source(*, source_id: str, deps: Any, settings: Settings) -> bool:
    """对结构 chunk 做 LLM 章节规划。成功替换 chunk 时返回 True；失败或未启用则保留原 chunk。"""
    if not settings.chunk_llm_segment:
        logger.debug("跳过章节规划 source=%s（chunk_llm_segment=false）", source_id)
        return False
    client = getattr(deps, "llm_client", None)
    if client is None or not client.is_configured:
        logger.debug("跳过章节规划 source=%s（LLM 未配置）", source_id)
        return False

    text = deps.knowledge.get_source_text(source_id)
    if text is None:
        logger.warning("跳过章节规划 source=%s：源正文不存在", source_id)
        return False

    chunks = deps.knowledge.list_chunks(source_id, status="active")
    if not chunks:
        logger.warning("跳过章节规划 source=%s：无 active chunk", source_id)
        return False

    spans = spans_from_chunks(chunks)
    sections = request_segmentation_plan(client, spans, settings)
    if sections is None:
        logger.warning("章节规划失败 source=%s，保留结构 chunk", source_id)
        return False

    drafts = apply_segmentation_plan(text, spans, sections)
    merged_chunks = build_segmented_source_chunks(source_id, text, drafts, sections)
    _persist_chunks(deps, source_id, merged_chunks, settings)
    logger.info(
        "章节规划完成 source=%s %s -> %s 段",
        source_id,
        len(chunks),
        len(merged_chunks),
    )
    return True


def _enrich_chunks_individually(*, kb_id: str, source_id: str, deps: Any, settings: Settings, client: Any) -> None:
    from dataclasses import replace

    chunks = deps.knowledge.list_chunks(source_id, status="active")
    if not chunks:
        return

    chunk_retrieval = getattr(deps, "chunk_retrieval", None)
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
                        "Chunk 元数据 enrich 失败 source=%s chunk=%s kb=%s",
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
        if chunk_retrieval is not None:
            chunk_retrieval.index_chunks([updated])

    _rebuild_topic_clusters(deps, kb_id, settings)
    _maybe_compile_wiki(kb_id=kb_id, source_id=source_id, deps=deps, settings=settings)
    logger.info("Chunk 元数据补全完成 source=%s kb=%s", source_id, kb_id)


@traceable(name="akos.enrich_chunks", run_type="chain")
def enrich_chunks(*, kb_id: str, source_id: str, deps: Any, settings: Settings) -> None:
    """Claim 入库后仅补 chunk 元数据，不改变切分边界。"""
    logger.info(
        "Chunk 元数据补全 开始 source=%s kb=%s llm_enrich=%s wiki=%s topic_cluster=%s",
        source_id,
        kb_id,
        settings.chunk_llm_enrich,
        getattr(settings, "wiki_compile", False),
        getattr(settings, "topic_cluster", False),
    )
    client = getattr(deps, "llm_client", None)
    configured = client is not None and client.is_configured
    if settings.chunk_llm_enrich and configured:
        _enrich_chunks_individually(kb_id=kb_id, source_id=source_id, deps=deps, settings=settings, client=client)
        return
    _rebuild_topic_clusters(deps, kb_id, settings)
    _maybe_compile_wiki(kb_id=kb_id, source_id=source_id, deps=deps, settings=settings)
