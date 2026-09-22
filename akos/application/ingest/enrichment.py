from __future__ import annotations

import logging
from typing import Any

from langsmith import traceable

from akos.application.ingest.document_anchor import resolve_document_anchor
from akos.application.ingest.domain_llm_extractor import DomainLlmExtractor
from akos.application.ingest.intersect import resolve_extraction_units
from akos.domain.ports.compiler import ExtractedClaim
from akos.application.ingest.spec_utils import apply_open_flag
from infra.settings import Settings

logger = logging.getLogger(__name__)


def ingest_graph_extracts_llm_claims(settings: Settings, deps: Any) -> bool:
    """判断 ingest 图的 compile_node 是否已按 chunk 跑过 LLM Claim 抽取。"""
    client = getattr(deps, "llm_client", None)
    domain = getattr(deps, "domain", None)
    return (
        settings.extract_llm
        and client is not None
        and client.is_configured
        and domain is not None
    )


@traceable(name="akos.enrich_source", run_type="chain")
def enrich_source(
    *,
    kb_id: str,
    source_id: str,
    deps: Any,
    settings: Settings,
) -> None:
    """compile 未抽取 Claim 时补抽（例如崩溃恢复后）。"""
    client = getattr(deps, "llm_client", None)
    if not settings.extract_llm or client is None or not client.is_configured:
        deps.knowledge.update_source_status(source_id, "succeeded")
        return

    deps.knowledge.update_source_status(source_id, "enriching")
    try:
        text = deps.knowledge.get_source_text(source_id)
        if text is None:
            raise RuntimeError(f"source text not found: {source_id}")

        source = deps.knowledge.get_source(source_id)
        document_anchor = resolve_document_anchor(
            text,
            title=getattr(source, "title", None) if source else None,
        )
        stored_chunks = deps.knowledge.list_chunks(source_id, status="active")
        units, truncated = resolve_extraction_units(
            text,
            settings,
            source_chunks=stored_chunks or None,
        )
        spec = apply_open_flag(deps.domain.llm_extraction_spec(), settings)
        extractor = DomainLlmExtractor(client, spec)
        extracted: list[ExtractedClaim] = []
        failed_chunks = 0

        for unit in units:
            for attempt in range(2):
                try:
                    extracted.extend(
                        extractor.extract(
                            unit.text,
                            document_anchor=document_anchor,
                            section_title=unit.title,
                            section_summary=unit.summary,
                        )
                    )
                    break
                except Exception:
                    if attempt == 1:
                        failed_chunks += 1

        deps.compiler.apply_extracted_claims(
            source_id,
            extracted,
            min_confidence=settings.extract_min_confidence,
            open_predicates=settings.extract_open_predicates,
        )
        logger.info(
            "补抽 Claim 完成 source=%s kb=%s extracted=%s units=%s failed_chunks=%s",
            source_id,
            kb_id,
            len(extracted),
            len(units),
            failed_chunks,
        )
        failure_ratio = failed_chunks / len(units) if units else 0.0
        final_status = "succeeded_partial" if truncated or failure_ratio >= 0.5 else "succeeded"
        deps.knowledge.update_source_status(source_id, final_status)
    except Exception:
        logger.exception("补抽 Claim 失败 source=%s kb=%s", source_id, kb_id)
        deps.knowledge.update_source_status(source_id, "failed")
        raise
