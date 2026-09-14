from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from knowledge.models import Claim, SourceChunk, TopicCluster
from knowledge.ports import KnowledgePort
from wiki.links import chunk_wikilink, source_wikilink, topic_page_name, topic_wikilink
from wiki.meta import WikiPageMeta, load_pages_meta, save_pages_meta
from wiki.paths import compile_wiki_root


@dataclass
class CompileReport:
    pages_written: int = 0
    topics: list[str] = field(default_factory=list)


def _format_frontmatter(kb_id: str, page_type: str = "topic") -> str:
    return "\n".join(
        [
            "---",
            f"tags: [{page_type}]",
            f"type: {page_type}",
            f"kb_id: {kb_id}",
            "---",
            "",
        ]
    )


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _clusters_for_source(knowledge: KnowledgePort, source_id: str) -> list[TopicCluster]:
    clusters = knowledge.list_topic_clusters(status="active")
    matched = [c for c in clusters if source_id in c.source_ids]
    if matched:
        return matched

    # Fallback: topics on active chunks for this source
    chunk_topics: set[str] = set()
    for chunk in knowledge.list_chunks(source_id, status="active"):
        chunk_topics.update(chunk.topics)
    if not chunk_topics:
        return []
    return [c for c in clusters if c.name in chunk_topics]


def _related_topic_names(clusters: list[TopicCluster], current: TopicCluster) -> list[str]:
    names = sorted({c.name for c in clusters if c.name != current.name})
    return names


def _render_topic_page(
    *,
    cluster: TopicCluster,
    claims: list[Claim],
    chunks: list[SourceChunk],
    source_titles: dict[str, str],
    related_topics: list[str],
    kb_id: str,
) -> str:
    lines = [
        _format_frontmatter(kb_id, "topic"),
        f"# {cluster.name}",
        "",
        "## 摘要",
    ]
    if cluster.summary:
        lines.append(f"> {cluster.summary}")
    else:
        lines.append("")
    lines.append("")

    lines.append("## Chunks")
    if not chunks:
        lines.append("- （无 Chunk）")
    else:
        for chunk in sorted(chunks, key=lambda item: (item.source_id, item.chunk_index)):
            label = chunk.title or f"chunk-{chunk.chunk_index}"
            summary = chunk.summary or chunk.text[:80]
            link = chunk_wikilink(chunk.source_id, chunk.chunk_index, label)
            lines.append(f"- {link}: {summary}")
    lines.append("")

    lines.append("## Claims")
    if not claims:
        lines.append("- （无 Claim）")
    else:
        for claim in sorted(claims, key=lambda item: (item.predicate, item.object)):
            source_id = claim.source_ids[0] if claim.source_ids else None
            if source_id:
                title = source_titles.get(source_id, source_id)
                prefix = f"{source_wikilink(source_id, title)}: "
            else:
                prefix = ""
            lines.append(f"- {prefix}{claim.predicate} → {claim.object}")
    lines.append("")

    lines.extend(["## 相关原文"])
    if not cluster.source_ids:
        lines.append("- （无原文）")
    else:
        for source_id in sorted(cluster.source_ids):
            title = source_titles.get(source_id, source_id)
            lines.append(f"- {source_wikilink(source_id, title)}")
    lines.append("")

    lines.extend(["## 相关主题"])
    if not related_topics:
        lines.append("- （无相关主题）")
    else:
        for name in related_topics:
            lines.append(f"- {topic_wikilink(name)}")
    lines.append("")
    return "\n".join(lines)


def _upsert_index_topics(wiki_root: Path, kb_id: str, topic_names: list[str]) -> None:
    index_path = wiki_root / "index.md"
    existing = index_path.read_text(encoding="utf-8") if index_path.is_file() else ""

    topic_block_lines = ["## 主题"]
    if topic_names:
        for name in sorted(set(topic_names)):
            topic_block_lines.append(f"- {topic_wikilink(name)}")
    else:
        topic_block_lines.append("- （无主题）")
    topic_block = "\n".join(topic_block_lines) + "\n"

    if "## 主题" in existing:
        # Replace existing topic section until next ## or EOF
        before, _, rest = existing.partition("## 主题")
        if "\n## " in rest:
            _, after_marker, after = rest.partition("\n## ")
            del after_marker
            new_content = before.rstrip() + "\n\n" + topic_block + "\n## " + after.lstrip()
            if not new_content.endswith("\n"):
                new_content += "\n"
        else:
            new_content = before.rstrip() + "\n\n" + topic_block
    elif existing.strip():
        new_content = existing.rstrip() + "\n\n" + topic_block
    else:
        new_content = "\n".join(
            [
                "---",
                "tags: [index]",
                "type: index",
                f"kb_id: {kb_id}",
                "---",
                "",
                f"# Wiki Index — {kb_id}",
                "",
                topic_block.rstrip(),
                "",
            ]
        )

    index_path.write_text(new_content if new_content.endswith("\n") else new_content + "\n", encoding="utf-8")


def compile_topics_for_source(
    knowledge: KnowledgePort,
    kb_id: str,
    source_id: str,
    data_root: str | Path,
    settings: Any,
    graph: Any = None,
) -> CompileReport:
    """Template-compile topic pages for topics touched by ``source_id`` (no LLM)."""
    del graph  # reserved for future cluster rebuild hook
    del settings  # LLM path is Task 5; template path ignores compile_llm here

    wiki_root = compile_wiki_root(data_root, kb_id)
    wiki_root.mkdir(parents=True, exist_ok=True)

    clusters = _clusters_for_source(knowledge, source_id)
    if not clusters:
        return CompileReport()

    all_active = knowledge.list_topic_clusters(status="active")
    sources = {s.id: s for s in knowledge.list_sources()}
    source_titles = {sid: src.title for sid, src in sources.items()}
    claims_by_id = {c.id: c for c in knowledge.get_claims_by_status("active")}

    chunks_by_id: dict[str, SourceChunk] = {}
    for src in sources.values():
        for chunk in knowledge.list_chunks(src.id, status="active"):
            chunks_by_id[chunk.id] = chunk

    pages_meta = load_pages_meta(wiki_root)
    written = 0
    topic_names: list[str] = []
    now = datetime.now(timezone.utc)

    for cluster in clusters:
        claims = [claims_by_id[cid] for cid in cluster.claim_ids if cid in claims_by_id]
        chunks = [chunks_by_id[cid] for cid in cluster.chunk_ids if cid in chunks_by_id]
        related = _related_topic_names(all_active, cluster)
        content = _render_topic_page(
            cluster=cluster,
            claims=claims,
            chunks=chunks,
            source_titles=source_titles,
            related_topics=related,
            kb_id=kb_id,
        )
        page_name = topic_page_name(cluster.name)
        page_path = wiki_root / f"{page_name}.md"
        page_path.write_text(content, encoding="utf-8")
        written += 1
        topic_names.append(cluster.name)

        pages_meta[page_name] = WikiPageMeta(
            path=f"{page_name}.md",
            title=cluster.name,
            kind="topic",
            content_hash=_content_hash(content),
            source_ids=list(cluster.source_ids),
            updated_at=now,
        )

    # Index lists all active topics known to knowledge (not only this compile)
    index_topics = sorted({c.name for c in all_active} | set(topic_names))
    _upsert_index_topics(wiki_root, kb_id, index_topics)
    save_pages_meta(wiki_root, pages_meta)

    return CompileReport(pages_written=written, topics=topic_names)
