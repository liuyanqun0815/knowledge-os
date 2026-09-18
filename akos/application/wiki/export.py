from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from akos.domain.ports.evidence import EvidencePort
from knowledge.models import Claim, Source, SourceChunk, TopicCluster
from akos.domain.ports.knowledge import KnowledgePort
from akos.application.wiki.hierarchy import HierarchyAssignment, assign_wiki_hierarchy
from akos.application.wiki.links import (
    entity_page_name,
    entity_wikilink,
    sanitize_filename,
    source_page_name,
    source_wikilink,
    topic_page_name,
    topic_page_path,
    topic_wikilink,
)

# Backward-compatible aliases for tests / callers that import private helpers.
_sanitize_filename = sanitize_filename
_source_page_name = source_page_name
_source_wikilink = source_wikilink
_entity_page_name = entity_page_name
_entity_wikilink = entity_wikilink
_topic_page_name = topic_page_name


def _topic_wikilink(
    name: str, *, hierarchy_enabled: bool = False, assignment: HierarchyAssignment | None = None
) -> str:
    """Topic wikilink: flat ``topic-`` or hub/leaf path when hierarchy is on."""
    if not hierarchy_enabled:
        return topic_wikilink(name, hierarchy_enabled=False)
    if assignment is not None:
        if assignment.role == "snippet":
            return topic_wikilink(assignment.hub, assignment.target_leaf, label=name)
        return topic_wikilink(assignment.hub, assignment.leaf, label=name)
    return topic_wikilink(name, hierarchy_enabled=False)


def _export_topic_rel_path(
    cluster_name: str, assignment: HierarchyAssignment | None, *, hierarchy_enabled: bool
) -> str:
    """Relative path without ``.md`` for a topic cluster page."""
    if not hierarchy_enabled or assignment is None:
        return topic_page_name(cluster_name)
    if assignment.role == "snippet":
        return topic_page_path(assignment.hub, assignment.target_leaf)
    if assignment.role == "hub" or assignment.leaf is None:
        return topic_page_path(assignment.hub, None)
    return topic_page_path(assignment.hub, assignment.leaf)


@dataclass
class WikiExportResult:
    kb_id: str
    output_dir: Path
    files_written: int
    source_pages: int
    entity_pages: int
    exported_at: datetime
    topic_pages: int = 0


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
            lines.append(f"- {_entity_wikilink(claim.subject)}: {claim.predicate} → {claim.object} " f"(`{claim.id}`)")

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


def _render_topic_page(
    cluster: TopicCluster,
    claims_by_id: dict[str, Claim],
    chunks_by_id: dict[str, SourceChunk],
    source_titles: dict[str, str],
    kb_id: str,
) -> str:
    lines = [
        _format_frontmatter(["topic"], "topic", kb_id),
        f"# {cluster.name}",
        "",
    ]
    if cluster.summary:
        lines.extend(["## 摘要", f"> {cluster.summary}", ""])

    lines.append("## Claims")
    claims = [claims_by_id[cid] for cid in cluster.claim_ids if cid in claims_by_id]
    if not claims:
        lines.append("- （无 Claim）")
    else:
        for claim in sorted(claims, key=lambda item: (item.predicate, item.object)):
            lines.append(_format_claim_line(claim, source_titles))

    chunks = [chunks_by_id[cid] for cid in cluster.chunk_ids if cid in chunks_by_id]
    if chunks:
        lines.extend(["", "## 章节"])
        for chunk in sorted(chunks, key=lambda item: (item.source_id, item.chunk_index)):
            label = chunk.title or f"chunk-{chunk.chunk_index}"
            page = f"chunk-{_sanitize_filename(chunk.source_id)}-{chunk.chunk_index}"
            lines.append(f"- [[{page}|{label}]]")

    if cluster.source_ids:
        lines.extend(["", "## 相关"])
        for source_id in sorted(cluster.source_ids):
            title = source_titles.get(source_id, source_id)
            lines.append(f"- {_source_wikilink(source_id, title)}")

    lines.append("")
    return "\n".join(lines)


def _render_index_page(
    kb_id: str,
    sources: list[Source],
    subjects: list[str],
    topics: list[str] | None = None,
    *,
    hierarchy_enabled: bool = False,
    assignments: dict[str, HierarchyAssignment] | None = None,
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

    topic_names = topics or []
    if topic_names:
        lines.extend(["", "## 主题"])
        for name in sorted(topic_names):
            assignment = (assignments or {}).get(name)
            lines.append(f"- {_topic_wikilink(name, hierarchy_enabled=hierarchy_enabled, assignment=assignment)}")

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
            f"({result.source_pages} sources, {result.entity_pages} entities"
            f", {result.topic_pages} topics)",
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
    graph=None,
) -> WikiExportResult:
    """Write markdown wiki pages from claims; optional LLM summaries on export."""
    del evidence  # reserved for future evidence excerpts on source pages

    if (
        settings is not None
        and getattr(settings, "topic_cluster", False)
        and graph is not None
        and not knowledge.list_topic_clusters()
    ):
        from knowledge.topic_service import rebuild_topic_clusters

        rebuild_topic_clusters(knowledge, graph, kb_id, settings)

    summarizer = None
    cache_dir = None
    if use_llm and llm_client is not None and getattr(llm_client, "is_configured", False):
        from akos.application.wiki.summarizer import WikiLlmSummarizer

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
    topic_pages = 0

    clusters = knowledge.list_topic_clusters(status="active")
    claims_by_id = {claim.id: claim for claim in active_claims}
    chunks_by_id: dict[str, SourceChunk] = {}
    for source in sources:
        for chunk in knowledge.list_chunks(source.id, status="active"):
            chunks_by_id[chunk.id] = chunk

    hierarchy_enabled = bool(settings is not None and getattr(settings, "wiki_hierarchy", False))
    assignments: dict[str, HierarchyAssignment] = {}
    if hierarchy_enabled and clusters:
        from domains.ecommerce_cs.wiki_hierarchy import get_ecommerce_wiki_seeds

        plan = assign_wiki_hierarchy([c.name for c in clusters], seeds=get_ecommerce_wiki_seeds())
        assignments = plan.assignments

    written_topic_paths: set[str] = set()
    for cluster in clusters:
        assignment = assignments.get(cluster.name)
        rel = _export_topic_rel_path(cluster.name, assignment, hierarchy_enabled=hierarchy_enabled)
        # Snippets fold into target pages; skip duplicate writes to same path
        if hierarchy_enabled and assignment is not None and assignment.role == "snippet":
            if rel in written_topic_paths:
                continue
        content = _render_topic_page(cluster, claims_by_id, chunks_by_id, source_titles, kb_id)
        out_path = output_dir / f"{rel}.md"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(content, encoding="utf-8")
        written_topic_paths.add(rel)
        files_written += 1
        topic_pages += 1

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
        topic_pages=topic_pages,
    )

    index_content = _render_index_page(
        kb_id,
        sources,
        list(claims_by_subject.keys()),
        topics=[cluster.name for cluster in clusters],
        hierarchy_enabled=hierarchy_enabled,
        assignments=assignments,
    )
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
        "topic_pages": result.topic_pages,
        "exported_at": result.exported_at.isoformat(),
    }
