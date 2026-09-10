from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from evidence.ports import EvidencePort
from knowledge.models import Claim, Source, SourceChunk
from knowledge.ports import KnowledgePort

_UNSAFE_FILENAME_CHARS = ('/', '\\', ':', '*', '?', '"', '<', '>', '|')


@dataclass
class WikiExportResult:
    kb_id: str
    output_dir: Path
    files_written: int
    source_pages: int
    entity_pages: int
    exported_at: datetime


def _sanitize_filename(name: str) -> str:
    result = name
    for char in _UNSAFE_FILENAME_CHARS:
        result = result.replace(char, "_")
    result = result.strip()
    return result or "unnamed"


def _source_page_name(source_id: str) -> str:
    return f"source-{_sanitize_filename(source_id)}"


def _source_wikilink(source_id: str, title: str | None = None) -> str:
    page = _source_page_name(source_id)
    label = title or source_id
    return f"[[{page}|{label}]]"


def _entity_page_name(subject: str) -> str:
    return _sanitize_filename(subject)


def _entity_wikilink(subject: str) -> str:
    return f"[[{_entity_page_name(subject)}|{subject}]]"


def _format_frontmatter(tags: list[str], page_type: str, kb_id: str) -> str:
    tag_str = ", ".join(tags)
    return "\n".join(
        [
            "---",
            f"tags: [{tag_str}]",
            f"type: {page_type}",
            f"kb_id: {kb_id}",
            "---",
            "",
        ]
    )


def _format_claim_line(claim: Claim, source_titles: dict[str, str]) -> str:
    source_id = claim.source_ids[0] if claim.source_ids else None
    if source_id:
        title = source_titles.get(source_id, source_id)
        prefix = f"{_source_wikilink(source_id, title)}: "
    else:
        prefix = ""
    return f"- {prefix}{claim.predicate} → {claim.object}"


def _render_entity_page(
    subject: str,
    claims: list[Claim],
    source_titles: dict[str, str],
    kb_id: str,
    summary: str | None = None,
) -> str:
    lines = [_format_frontmatter(["entity"], "entity", kb_id), f"# {subject}", ""]
    if summary:
        lines.extend(["## 摘要", f"> {summary}", ""])
    lines.extend(["## Claims"])
    for claim in sorted(claims, key=lambda item: (item.predicate, item.object)):
        lines.append(_format_claim_line(claim, source_titles))

    related_source_ids = sorted({source_id for claim in claims for source_id in claim.source_ids})
    if related_source_ids:
        lines.extend(["", "## 相关"])
        for source_id in related_source_ids:
            title = source_titles.get(source_id, source_id)
            lines.append(f"- {_source_wikilink(source_id, title)}")

    lines.append("")
    return "\n".join(lines)


def _render_source_page(
    source: Source,
    claims: list[Claim],
    chunks: list[SourceChunk],
    kb_id: str,
    summary: str | None = None,
) -> str:
    lines = [
        _format_frontmatter(["source"], "source", kb_id),
        f"# {source.title}",
        "",
    ]
    if summary:
        lines.extend(["## 摘要", f"> {summary}", ""])
    lines.extend(
        [
            "## 元数据",
            f"- source_id: `{source.id}`",
            f"- type: {source.type}",
            f"- status: {source.status}",
            f"- chunks: {len(chunks)}",
            "",
            "## Claims",
        ]
    )
    active_claims = [claim for claim in claims if claim.status == "active"]
    if not active_claims:
        lines.append("- （无 active Claim）")
    else:
        for claim in sorted(active_claims, key=lambda item: (item.subject, item.predicate)):
            lines.append(
                f"- {_entity_wikilink(claim.subject)}: {claim.predicate} → {claim.object} "
                f"(`{claim.id}`)"
            )

    if chunks:
        lines.extend(["", "## 章节"])
        for chunk in sorted(chunks, key=lambda item: item.chunk_index):
            label = chunk.title or f"chunk-{chunk.chunk_index}"
            page = f"chunk-{_sanitize_filename(source.id)}-{chunk.chunk_index}"
            lines.append(f"- [[{page}|{label}]]")

    lines.append("")
    return "\n".join(lines)


def _render_chunk_page(source: Source, chunk: SourceChunk, kb_id: str) -> str:
    title = chunk.title or f"Chunk {chunk.chunk_index}"
    lines = [
        _format_frontmatter(["chunk"], "chunk", kb_id),
        f"# {title}",
        "",
        f"- source: {_source_wikilink(source.id, source.title)}",
        f"- chunk_index: {chunk.chunk_index}",
        "",
        chunk.text,
        "",
    ]
    return "\n".join(lines)


def _render_index_page(
    kb_id: str,
    sources: list[Source],
    subjects: list[str],
) -> str:
    lines = [
        _format_frontmatter(["index"], "index", kb_id),
        f"# Wiki Index — {kb_id}",
        "",
        "## Sources",
    ]
    if not sources:
        lines.append("- （无文档）")
    else:
        for source in sorted(sources, key=lambda item: item.title):
            lines.append(f"- {_source_wikilink(source.id, source.title)}")

    lines.extend(["", "## Entities"])
    if not subjects:
        lines.append("- （无实体）")
    else:
        for subject in sorted(subjects):
            lines.append(f"- {_entity_wikilink(subject)}")

    lines.append("")
    return "\n".join(lines)


def _render_log_page(kb_id: str, result: WikiExportResult) -> str:
    return "\n".join(
        [
            _format_frontmatter(["log"], "log", kb_id),
            "# Export Log",
            "",
            f"- {result.exported_at.isoformat()}: exported {result.files_written} files "
            f"({result.source_pages} sources, {result.entity_pages} entities)",
            "",
        ]
    )


def export_wiki(
    knowledge: KnowledgePort,
    evidence: EvidencePort,
    kb_id: str,
    output_dir: Path,
    *,
    use_llm: bool = False,
    llm_client=None,
    settings=None,
) -> WikiExportResult:
    """Write markdown wiki pages from claims; optional LLM summaries on export."""
    del evidence  # reserved for future evidence excerpts on source pages

    summarizer = None
    cache_dir = None
    if use_llm and llm_client is not None and getattr(llm_client, "is_configured", False):
        from wiki.summarizer import WikiLlmSummarizer

        cache_dir = output_dir / ".cache"
        prompt_version = getattr(settings, "wiki_prompt_version", "v1") if settings else "v1"
        use_cache = getattr(settings, "wiki_llm_cache", True) if settings else True
        summarizer = WikiLlmSummarizer(
            llm_client,
            cache_dir=cache_dir,
            prompt_version=prompt_version,
            use_cache=use_cache,
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    exported_at = datetime.now(timezone.utc)

    sources = knowledge.list_sources()
    source_titles = {source.id: source.title for source in sources}
    active_claims = knowledge.get_claims_by_status("active")

    claims_by_subject: dict[str, list[Claim]] = defaultdict(list)
    for claim in active_claims:
        claims_by_subject[claim.subject].append(claim)

    files_written = 0
    source_pages = 0
    entity_pages = 0

    for source in sources:
        claims = knowledge.get_claims_for_source(source.id)
        chunks = knowledge.list_chunks(source.id, status="active")
        summary = None
        if summarizer is not None:
            summary = summarizer.summarize_source(source, claims, chunks)
        page_name = _source_page_name(source.id)
        content = _render_source_page(source, claims, chunks, kb_id, summary=summary)
        (output_dir / f"{page_name}.md").write_text(content, encoding="utf-8")
        files_written += 1
        source_pages += 1
        for chunk in chunks:
            chunk_page = f"chunk-{_sanitize_filename(source.id)}-{chunk.chunk_index}"
            chunk_content = _render_chunk_page(source, chunk, kb_id)
            (output_dir / f"{chunk_page}.md").write_text(chunk_content, encoding="utf-8")
            files_written += 1

    for subject, claims in claims_by_subject.items():
        page_name = _entity_page_name(subject)
        related_chunks: list[SourceChunk] = []
        source_ids = {source_id for claim in claims for source_id in claim.source_ids}
        for source_id in source_ids:
            related_chunks.extend(knowledge.list_chunks(source_id, status="active"))
        summary = None
        if summarizer is not None:
            summary = summarizer.summarize_entity(subject, claims, related_chunks)
        content = _render_entity_page(subject, claims, source_titles, kb_id, summary=summary)
        (output_dir / f"{page_name}.md").write_text(content, encoding="utf-8")
        files_written += 1
        entity_pages += 1

    result = WikiExportResult(
        kb_id=kb_id,
        output_dir=output_dir,
        files_written=files_written,
        source_pages=source_pages,
        entity_pages=entity_pages,
        exported_at=exported_at,
    )

    index_content = _render_index_page(kb_id, sources, list(claims_by_subject.keys()))
    (output_dir / "index.md").write_text(index_content, encoding="utf-8")
    files_written += 1

    log_content = _render_log_page(kb_id, result)
    (output_dir / "log.md").write_text(log_content, encoding="utf-8")
    files_written += 1

    result.files_written = files_written
    return result


def resolve_wiki_output_dir(data_root: str, kb_id: str, output_dir: str | None = None) -> Path:
    base = Path(data_root).resolve()
    if output_dir:
        target = (base / output_dir).resolve()
        if base not in target.parents and target != base:
            raise ValueError("output_dir must stay under data root")
        return target
    return base / kb_id / "wiki"


def wiki_export_result_to_dict(result: WikiExportResult) -> dict:
    return {
        "kb_id": result.kb_id,
        "output_path": str(result.output_dir),
        "files_written": result.files_written,
        "source_pages": result.source_pages,
        "entity_pages": result.entity_pages,
        "exported_at": result.exported_at.isoformat(),
    }
