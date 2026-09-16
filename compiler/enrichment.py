from __future__ import annotations

import logging
from typing import Any

from langsmith import traceable

from compiler.chunker import chunk_text
from compiler.document_anchor import resolve_document_anchor
from compiler.domain_llm_extractor import DomainLlmExtractor
from compiler.ports import ExtractedClaim
from compiler.spec_utils import apply_open_flag
from infra.settings import Settings

logger = logging.getLogger(__name__)


@traceable(name="akos.enrich_source", run_type="chain")
def enrich_source(
    *,
    kb_id: str,
    source_id: str,
    deps: Any,
    settings: Settings,
) -> None:
    """Backfill one source with claims extracted by the configured LLM."""
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
        anchor = resolve_document_anchor(
            text,
            title=getattr(source, "title", None) if source else None,
        )
        result = chunk_text(
            text,
            max_chars=settings.chunk_max_chars,
            max_chunks=settings.chunk_max_per_doc,
        )
        spec = apply_open_flag(deps.domain.llm_extraction_spec(), settings)
        extractor = DomainLlmExtractor(client, spec)
        extracted: list[ExtractedClaim] = []
        failed_chunks = 0

        for chunk in result.chunks:
            for attempt in range(2):
                try:
                    extracted.extend(extractor.extract(chunk, document_anchor=anchor))
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
            "LLM enrichment finished for source %s in kb %s: extracted=%s claims",
            source_id,
            kb_id,
            len(extracted),
        )
        failure_ratio = failed_chunks / len(result.chunks) if result.chunks else 0.0
        final_status = "succeeded_partial" if result.truncated or failure_ratio >= 0.5 else "succeeded"
        deps.knowledge.update_source_status(source_id, final_status)
    except Exception:
        logger.exception("LLM enrichment failed for source %s in kb %s", source_id, kb_id)
        deps.knowledge.update_source_status(source_id, "failed")
        raise
