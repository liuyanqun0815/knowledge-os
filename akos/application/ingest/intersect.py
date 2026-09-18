from __future__ import annotations

import logging
from dataclasses import dataclass

from akos.application.ingest.chunker import chunk_document, chunk_text
from akos.application.ingest.document_anchor import resolve_document_anchor
from akos.application.ingest.domain_llm_extractor import DomainLlmExtractor
from compiler.ports import ExtractedClaim
from akos.application.ingest.spec_utils import apply_open_flag
from infra.settings import Settings
from ontology.ports import OntologyPort

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExtractionUnit:
    text: str
    title: str | None = None


def claim_triple_key(
    subject: str,
    predicate: str,
    object_value: str,
    ontology: OntologyPort | None = None,
) -> tuple[str, str, str]:
    if ontology is not None:
        subject = ontology.normalize_term(subject)
        object_value = ontology.normalize_term(object_value)
    return (subject.strip(), predicate.strip(), object_value.strip())


def intersect_extracted(
    rule_claims: list[ExtractedClaim],
    llm_claims: list[ExtractedClaim],
    ontology: OntologyPort | None = None,
) -> list[ExtractedClaim]:
    """Keep claims whose (subject, predicate, object) triple appears in both rule and LLM results."""
    llm_by_triple = {
        claim_triple_key(claim.subject, claim.predicate, claim.object, ontology): claim for claim in llm_claims
    }
    merged: list[ExtractedClaim] = []
    for rule in rule_claims:
        key = claim_triple_key(rule.subject, rule.predicate, rule.object, ontology)
        llm = llm_by_triple.get(key)
        if llm is None:
            continue
        merged.append(
            ExtractedClaim(
                subject=rule.subject,
                predicate=rule.predicate,
                object=rule.object,
                confidence=min(1.0, max(rule.confidence, llm.confidence)),
                quote=rule.quote,
                start=rule.start,
                end=rule.end,
            )
        )
    return merged


def _merge_duplicate_triple(rule: ExtractedClaim, llm: ExtractedClaim) -> ExtractedClaim:
    """Prefer rule quote/span when both channels agree on the same triple."""
    quote = rule.quote or llm.quote
    start = rule.start if rule.quote else llm.start
    end = rule.end if rule.quote else llm.end
    return ExtractedClaim(
        subject=rule.subject,
        predicate=rule.predicate,
        object=rule.object,
        confidence=min(1.0, max(rule.confidence, llm.confidence)),
        quote=quote,
        start=start,
        end=end,
    )


def union_extracted(
    rule_claims: list[ExtractedClaim],
    llm_claims: list[ExtractedClaim],
    ontology: OntologyPort | None = None,
) -> list[ExtractedClaim]:
    """Merge rule and LLM claims; dedupe by triple, preferring rule evidence spans on overlap."""
    merged: dict[tuple[str, str, str], ExtractedClaim] = {}
    for rule in rule_claims:
        key = claim_triple_key(rule.subject, rule.predicate, rule.object, ontology)
        merged[key] = rule
    for llm in llm_claims:
        key = claim_triple_key(llm.subject, llm.predicate, llm.object, ontology)
        existing = merged.get(key)
        if existing is None:
            merged[key] = llm
        else:
            merged[key] = _merge_duplicate_triple(existing, llm)
    return list(merged.values())


def units_from_source_chunks(chunks: list) -> list[ExtractionUnit]:
    """Convert stored SourceChunk rows into extraction units (title = subject anchor)."""
    ordered = sorted(chunks, key=lambda item: getattr(item, "chunk_index", 0))
    return [ExtractionUnit(text=chunk.text, title=getattr(chunk, "title", None)) for chunk in ordered if chunk.text]


def resolve_extraction_units(
    text: str,
    settings: Settings,
    *,
    source_chunks: list | None = None,
) -> tuple[list[ExtractionUnit], bool]:
    """Prefer finalized source_chunks; otherwise chunk with the configured document mode."""
    if source_chunks:
        return units_from_source_chunks(source_chunks), False

    mode = settings.chunk_mode
    heading_level = settings.chunk_heading_level
    try:
        result = chunk_document(
            text,
            max_chars=settings.chunk_max_chars,
            max_chunks=settings.chunk_max_per_doc,
            mode=mode,
            heading_level=heading_level,
        )
        units = [ExtractionUnit(text=draft.text, title=draft.title) for draft in result.chunks]
        return units, result.truncated
    except Exception:
        # Keep older chunk_text path if document chunker fails unexpectedly.
        legacy = chunk_text(
            text,
            max_chars=settings.chunk_max_chars,
            max_chunks=settings.chunk_max_per_doc,
        )
        return [ExtractionUnit(text=piece) for piece in legacy.chunks], legacy.truncated


def extract_llm_claims_from_text(
    text: str,
    llm_client,
    domain,
    settings: Settings,
    *,
    title: str | None = None,
    source_chunks: list | None = None,
) -> list[ExtractedClaim]:
    """Extract LLM claims from text, preferring finalized source_chunks when available."""
    extractor = DomainLlmExtractor(llm_client, apply_open_flag(domain.llm_extraction_spec(), settings))
    document_anchor = resolve_document_anchor(text, title=title)
    units, _truncated = resolve_extraction_units(text, settings, source_chunks=source_chunks)

    claims: list[ExtractedClaim] = []
    seen: set[tuple[str, str, str]] = set()
    for unit in units:
        # Section title (e.g. product heading) is a stronger subject anchor than doc-level name.
        unit_anchor = (unit.title or "").strip() or document_anchor
        for claim in extractor.extract(unit.text, document_anchor=unit_anchor):
            key = (claim.subject.strip(), claim.predicate.strip(), claim.object.strip())
            if key in seen:
                continue
            seen.add(key)
            claims.append(claim)
    return claims


def select_hybrid_candidates(
    text: str,
    *,
    rule_extractor,
    llm_client,
    domain,
    settings: Settings,
    ontology: OntologyPort | None = None,
    title: str | None = None,
    source_chunks: list | None = None,
) -> list[ExtractedClaim]:
    """Combine rule and LLM extraction according to AKOS_EXTRACT_RULES / AKOS_EXTRACT_LLM settings."""
    rule_claims = rule_extractor.extract(text) if settings.extract_rules else []
    use_llm = settings.extract_llm and llm_client is not None and llm_client.is_configured and domain is not None
    if not use_llm:
        return rule_claims

    try:
        llm_claims = extract_llm_claims_from_text(
            text,
            llm_client,
            domain,
            settings,
            title=title,
            source_chunks=source_chunks,
        )
    except Exception:
        if settings.extract_rules and rule_claims:
            logger.exception(
                "LLM extraction failed; falling back to %s rule claims",
                len(rule_claims),
            )
            return rule_claims
        raise
    if settings.extract_rules and settings.extract_llm:
        return union_extracted(rule_claims, llm_claims, ontology)
    return llm_claims
