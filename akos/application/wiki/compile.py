from __future__ import annotations

import hashlib
import json
import logging
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from akos.domains.ecommerce_cs.wiki_hierarchy import get_ecommerce_wiki_seeds
from akos.domain.models.knowledge import Claim, SourceChunk, TopicCluster
from akos.domain.ports.knowledge import KnowledgePort
from akos.application.wiki.hierarchy import HierarchyAssignment, HierarchyPlan, assign_wiki_hierarchy
from akos.application.wiki.links import (
    chunk_wikilink,
    entity_wikilink,
    source_wikilink,
    topic_page_name,
    topic_page_path,
    topic_wikilink,
)
from akos.application.wiki.source_plan import compile_source_wiki_for_source
from akos.application.wiki.meta import WikiPageMeta, load_pages_meta, save_pages_meta
from akos.application.wiki.paths import compile_wiki_root
from akos.application.wiki.prompts import build_topic_merge_prompt

logger = logging.getLogger(__name__)


@dataclass
class CompileReport:
    pages_written: int = 0
    topics: list[str] = field(default_factory=list)


@dataclass
class _PageBundle:
    hub: str
    leaf: str | None  # None => hub _index
    title: str
    role: str  # hub | leaf
    claims: list[Claim] = field(default_factory=list)
    chunks: list[SourceChunk] = field(default_factory=list)
    source_ids: set[str] = field(default_factory=set)
    summaries: list[str] = field(default_factory=list)
    raw_topics: list[str] = field(default_factory=list)


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
    title: str,
    summary: str,
    claims: list[Claim],
    chunks: list[SourceChunk],
    source_ids: list[str],
    source_titles: dict[str, str],
    related_links: list[str],
    kb_id: str,
    page_type: str = "topic",
) -> str:
    lines = [
        _format_frontmatter(kb_id, page_type),
        f"# {title}",
        "",
        "## 摘要",
    ]
    if summary:
        lines.append(f"> {summary}")
    else:
        lines.append("")
    lines.append("")

    lines.append("## Chunks")
    if not chunks:
        lines.append("- （无 Chunk）")
    else:
        for chunk in sorted(chunks, key=lambda item: (item.source_id, item.chunk_index)):
            label = chunk.title or f"chunk-{chunk.chunk_index}"
            summary_text = chunk.summary or chunk.text[:80]
            link = chunk_wikilink(chunk.source_id, chunk.chunk_index, label)
            lines.append(f"- {link}: {summary_text}")
    lines.append("")

    lines.append("## Claims")
    if not claims:
        lines.append("- （无 Claim）")
    else:
        for claim in sorted(claims, key=lambda item: (item.predicate, item.object)):
            source_id = claim.source_ids[0] if claim.source_ids else None
            if source_id:
                src_title = source_titles.get(source_id, source_id)
                prefix = f"{source_wikilink(source_id, src_title)}: "
            else:
                prefix = ""
            lines.append(f"- {prefix}{claim.predicate} → {claim.object}")
    lines.append("")

    lines.extend(["## 相关原文"])
    if not source_ids:
        lines.append("- （无原文）")
    else:
        for source_id in sorted(source_ids):
            src_title = source_titles.get(source_id, source_id)
            lines.append(f"- {source_wikilink(source_id, src_title)}")
    lines.append("")

    entities: set[str] = set()
    for claim in claims:
        if claim.subject:
            entities.add(claim.subject)
        if claim.object:
            entities.add(claim.object)

    lines.extend(["## 相关实体"])
    if not entities:
        lines.append("- （无相关实体）")
    else:
        for name in sorted(entities):
            lines.append(f"- {entity_wikilink(name)}")
    lines.append("")

    lines.extend(["## 相关主题"])
    if not related_links:
        lines.append("- （无相关主题）")
    else:
        for link in related_links:
            lines.append(f"- {link}")
    lines.append("")
    return "\n".join(lines)


def _strip_json_fence(content: str) -> str:
    stripped = content.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    return stripped.strip()


def _parse_llm_markdown(raw: str) -> str | None:
    try:
        payload = json.loads(_strip_json_fence(raw))
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(payload, dict):
        return None
    markdown = payload.get("markdown")
    if not isinstance(markdown, str) or not markdown.strip():
        return None
    return markdown.strip()


def _required_wikilinks_present(body: str, required: list[str]) -> bool:
    return all(link in body for link in required)


def _llm_client_ready(settings: Any, llm_client: Any) -> bool:
    if not getattr(settings, "wiki_compile_llm", False):
        return False
    if llm_client is None:
        return False
    return bool(getattr(llm_client, "is_configured", False))


def _evidence_payload(
    *,
    topic_name: str,
    summary: str,
    claims: list[Claim],
    chunks: list[SourceChunk],
    source_ids: list[str],
    source_titles: dict[str, str],
) -> dict[str, Any]:
    return {
        "topic": topic_name,
        "summary": summary,
        "chunks": [
            {
                "source_id": c.source_id,
                "chunk_index": c.chunk_index,
                "title": c.title,
                "summary": c.summary,
                "excerpt": (c.text or "")[:200],
            }
            for c in chunks
        ],
        "claims": [
            {
                "subject": claim.subject,
                "predicate": claim.predicate,
                "object": claim.object,
                "source_ids": list(claim.source_ids),
            }
            for claim in claims
        ],
        "sources": [{"id": sid, "title": source_titles.get(sid, sid)} for sid in sorted(source_ids)],
    }


def _required_links_for_page(
    *,
    claims: list[Claim],
    source_ids: list[str],
    source_titles: dict[str, str],
    related_links: list[str],
) -> list[str]:
    links: list[str] = []
    for source_id in sorted(source_ids):
        links.append(source_wikilink(source_id, source_titles.get(source_id, source_id)))
    for claim in claims:
        if claim.subject:
            links.append(entity_wikilink(claim.subject))
        if claim.object:
            links.append(entity_wikilink(claim.object))
    links.extend(related_links)
    seen: set[str] = set()
    ordered: list[str] = []
    for link in links:
        if link not in seen:
            seen.add(link)
            ordered.append(link)
    return ordered


def _try_llm_merge(
    *,
    llm_client: Any,
    topic_name: str,
    old_body: str,
    template_body: str,
    claims: list[Claim],
    chunks: list[SourceChunk],
    source_ids: list[str],
    source_titles: dict[str, str],
    related_links: list[str],
) -> str | None:
    required = _required_links_for_page(
        claims=claims,
        source_ids=source_ids,
        source_titles=source_titles,
        related_links=related_links,
    )
    source_links = [source_wikilink(sid, source_titles.get(sid, sid)) for sid in sorted(source_ids)]
    prompt = build_topic_merge_prompt(
        topic_name=topic_name,
        old_body=old_body or template_body,
        evidence=_evidence_payload(
            topic_name=topic_name,
            summary="",
            claims=claims,
            chunks=chunks,
            source_ids=source_ids,
            source_titles=source_titles,
        ),
        required_wikilinks=required,
    )
    try:
        raw = llm_client.chat_completions([{"role": "user", "content": prompt}], temperature=0.2)
    except Exception:
        logger.exception("Wiki 主题页 LLM 合并失败 topic=%s", topic_name)
        return None
    markdown = _parse_llm_markdown(raw)
    if markdown is None:
        return None
    if not _required_wikilinks_present(markdown, source_links):
        return None
    for section in ("## 相关原文", "## 相关实体", "## 相关主题"):
        if section not in markdown:
            return None
    return markdown


def _upsert_index_topics(wiki_root: Path, kb_id: str, topic_names: list[str]) -> None:
    """Flat index: bullet list of legacy topic- links."""
    index_path = wiki_root / "index.md"
    existing = index_path.read_text(encoding="utf-8") if index_path.is_file() else ""

    topic_block_lines = ["## 主题"]
    if topic_names:
        for name in sorted(set(topic_names)):
            topic_block_lines.append(f"- {topic_wikilink(name, hierarchy_enabled=False)}")
    else:
        topic_block_lines.append("- （无主题）")
    topic_block = "\n".join(topic_block_lines) + "\n"
    _write_index_section(index_path, existing, kb_id, topic_block)


def _upsert_index_hubs(
    wiki_root: Path,
    kb_id: str,
    hubs: dict[str, list[str]],
) -> None:
    """Hierarchy index: group leaf links under each hub."""
    index_path = wiki_root / "index.md"
    existing = index_path.read_text(encoding="utf-8") if index_path.is_file() else ""

    lines = ["## 主题"]
    if not hubs:
        lines.append("- （无主题）")
    else:
        for hub in sorted(hubs):
            lines.append("")
            lines.append(f"### {hub}")
            lines.append(f"- {topic_wikilink(hub)}")
            for leaf in sorted(hubs[hub]):
                lines.append(f"- {topic_wikilink(hub, leaf)}")
    topic_block = "\n".join(lines) + "\n"
    _write_index_section(index_path, existing, kb_id, topic_block)


def _write_index_section(index_path: Path, existing: str, kb_id: str, topic_block: str) -> None:
    if "## 主题" in existing:
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


def _delete_flat_topic_pages(wiki_root: Path) -> None:
    for path in wiki_root.glob("topic-*.md"):
        if path.is_file():
            path.unlink()


def _page_key(hub: str, leaf: str | None) -> tuple[str, str | None]:
    return (hub, leaf)


def _target_for_assignment(a: HierarchyAssignment) -> tuple[str, str | None, str, str]:
    """Return (hub, leaf, title, role) for where content should land."""
    if a.role == "snippet":
        return (a.hub, a.target_leaf, a.target_leaf or a.hub, "leaf" if a.target_leaf else "hub")
    if a.role == "hub" or a.leaf is None:
        return (a.hub, None, a.hub, "hub")
    return (a.hub, a.leaf, a.leaf, "leaf")


def _related_links_for_page(
    *,
    hub: str,
    leaf: str | None,
    plan: HierarchyPlan,
    max_related: int,
) -> list[str]:
    links: list[str] = []
    if leaf is not None:
        links.append(topic_wikilink(hub))
        for other in plan.hubs.get(hub, []):
            if other == leaf:
                continue
            links.append(topic_wikilink(hub, other))
    else:
        for child in plan.hubs.get(hub, []):
            links.append(topic_wikilink(hub, child))
    return links[: max(0, max_related)]


def _merge_into_bundle(
    bundles: dict[tuple[str, str | None], _PageBundle],
    *,
    hub: str,
    leaf: str | None,
    title: str,
    role: str,
    claims: list[Claim],
    chunks: list[SourceChunk],
    source_ids: list[str],
    summary: str,
    raw_topic: str,
) -> None:
    key = _page_key(hub, leaf)
    bundle = bundles.get(key)
    if bundle is None:
        bundle = _PageBundle(hub=hub, leaf=leaf, title=title, role=role)
        bundles[key] = bundle
    bundle.claims.extend(claims)
    bundle.chunks.extend(chunks)
    bundle.source_ids.update(source_ids)
    if summary:
        bundle.summaries.append(summary)
    bundle.raw_topics.append(raw_topic)


def _build_hierarchy_plan(names: list[str]) -> HierarchyPlan:
    seeds = get_ecommerce_wiki_seeds()
    return assign_wiki_hierarchy(names, seeds=seeds)


def _compile_hierarchy_for_source(
    knowledge: KnowledgePort,
    kb_id: str,
    source_id: str,
    wiki_root: Path,
    settings: Any,
    llm_client: Any = None,
) -> CompileReport:
    clusters = _clusters_for_source(knowledge, source_id)
    if not clusters:
        return CompileReport()

    all_active = knowledge.list_topic_clusters(status="active")
    plan = _build_hierarchy_plan([c.name for c in all_active])
    touched_names = {c.name for c in clusters}

    sources = {s.id: s for s in knowledge.list_sources()}
    source_titles = {sid: src.title for sid, src in sources.items()}
    claims_by_id = {c.id: c for c in knowledge.get_claims_by_status("active")}
    chunks_by_id: dict[str, SourceChunk] = {}
    for src in sources.values():
        for chunk in knowledge.list_chunks(src.id, status="active"):
            chunks_by_id[chunk.id] = chunk

    clusters_by_name = {c.name: c for c in all_active}
    bundles: dict[tuple[str, str | None], _PageBundle] = {}

    # Fold every active cluster whose content affects a page touched by this source
    pages_needed: set[tuple[str, str | None]] = set()
    for name in touched_names:
        assignment = plan.assignments.get(name)
        if assignment is None:
            continue
        hub, leaf, _title, _role = _target_for_assignment(assignment)
        pages_needed.add(_page_key(hub, leaf))
        pages_needed.add(_page_key(hub, None))  # always refresh hub index

    for name, assignment in plan.assignments.items():
        hub, leaf, title, role = _target_for_assignment(assignment)
        if _page_key(hub, leaf) not in pages_needed and _page_key(hub, None) not in pages_needed:
            continue
        # Only fold cluster content when the target page is needed
        if _page_key(hub, leaf) not in pages_needed:
            continue
        cluster = clusters_by_name.get(name)
        if cluster is None:
            continue
        claims = [claims_by_id[cid] for cid in cluster.claim_ids if cid in claims_by_id]
        chunks = [chunks_by_id[cid] for cid in cluster.chunk_ids if cid in chunks_by_id]
        _merge_into_bundle(
            bundles,
            hub=hub,
            leaf=leaf,
            title=title,
            role=role,
            claims=claims,
            chunks=chunks,
            source_ids=list(cluster.source_ids),
            summary=cluster.summary or "",
            raw_topic=name,
        )

    # Ensure hub index bundles exist for every needed hub
    for hub, leaf in list(pages_needed):
        if leaf is not None:
            continue
        key = _page_key(hub, None)
        if key not in bundles:
            bundles[key] = _PageBundle(hub=hub, leaf=None, title=hub, role="hub")

    # Child links on hub: ensure hub leaf list includes folded snippet targets
    hubs_for_index: dict[str, list[str]] = defaultdict(list)
    for hub, leaves in plan.hubs.items():
        hubs_for_index[hub] = list(leaves)
    for (hub, leaf), bundle in bundles.items():
        if leaf and leaf not in hubs_for_index[hub]:
            hubs_for_index[hub].append(leaf)
    # Also include all plan hubs that appear in pages_needed
    for hub, _leaf in pages_needed:
        hubs_for_index.setdefault(hub, list(plan.hubs.get(hub, [])))

    pages_meta = load_pages_meta(wiki_root)
    written = 0
    topic_names: list[str] = []
    now = datetime.now(timezone.utc)
    use_llm = _llm_client_ready(settings, llm_client)
    max_related = int(getattr(settings, "wiki_max_related", 12) or 12)

    for (hub, leaf), bundle in sorted(bundles.items(), key=lambda item: (item[0][0], item[0][1] or "")):
        if _page_key(hub, leaf) not in pages_needed:
            continue
        # Deduplicate claims/chunks by id
        claims = list({c.id: c for c in bundle.claims}.values())
        chunks = list({c.id: c for c in bundle.chunks}.values())
        source_ids = sorted(bundle.source_ids)
        summary = "；".join(dict.fromkeys(bundle.summaries)) if bundle.summaries else ""
        related = _related_links_for_page(hub=hub, leaf=leaf, plan=plan, max_related=max_related)

        # Hub index: prepend child outline into summary area via related only; add child section in body
        page_type = "hub" if leaf is None else "topic"
        template_body = _render_topic_page(
            title=bundle.title,
            summary=summary,
            claims=claims,
            chunks=chunks,
            source_ids=source_ids,
            source_titles=source_titles,
            related_links=related,
            kb_id=kb_id,
            page_type=page_type,
        )
        if leaf is None:
            # Insert child links section after summary for hub pages
            child_lines = ["## 子主题"]
            children = hubs_for_index.get(hub, [])
            if not children:
                child_lines.append("- （无子主题）")
            else:
                for child in sorted(children):
                    child_lines.append(f"- {topic_wikilink(hub, child)}")
            child_block = "\n".join(child_lines) + "\n\n"
            template_body = template_body.replace("## Chunks", child_block + "## Chunks", 1)

        rel_path = topic_page_path(hub, leaf) + ".md"
        page_path = wiki_root / rel_path
        page_path.parent.mkdir(parents=True, exist_ok=True)
        old_body = page_path.read_text(encoding="utf-8") if page_path.is_file() else ""

        content = template_body
        if use_llm and leaf is not None:
            merged = _try_llm_merge(
                llm_client=llm_client,
                topic_name=bundle.title,
                old_body=old_body,
                template_body=template_body,
                claims=claims,
                chunks=chunks,
                source_ids=source_ids,
                source_titles=source_titles,
                related_links=related,
            )
            if merged is not None:
                content = merged
            else:
                logger.info("Wiki 主题页 LLM 失败，回退模板 topic=%s", bundle.title)

        page_path.write_text(content, encoding="utf-8")
        written += 1
        topic_names.extend(bundle.raw_topics)

        page_id = topic_page_path(hub, leaf)
        pages_meta[page_id] = WikiPageMeta(
            path=rel_path.replace("\\", "/"),
            title=bundle.title,
            kind=page_type,
            content_hash=_content_hash(content),
            source_ids=source_ids,
            updated_at=now,
            hub=hub,
            role="hub" if leaf is None else "leaf",
        )

    if getattr(settings, "wiki_migrate_flat", True):
        _delete_flat_topic_pages(wiki_root)

    # Index: all hubs from full plan (stable catalog)
    index_hubs = {h: list(leaves) for h, leaves in plan.hubs.items()}
    for hub, leaves in hubs_for_index.items():
        index_hubs.setdefault(hub, [])
        for leaf in leaves:
            if leaf not in index_hubs[hub]:
                index_hubs[hub].append(leaf)
    _upsert_index_hubs(wiki_root, kb_id, index_hubs)
    save_pages_meta(wiki_root, pages_meta)

    return CompileReport(pages_written=written, topics=sorted(set(topic_names)))


def _compile_flat_for_source(
    knowledge: KnowledgePort,
    kb_id: str,
    source_id: str,
    wiki_root: Path,
    settings: Any,
    llm_client: Any = None,
) -> CompileReport:
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
    use_llm = _llm_client_ready(settings, llm_client)

    for cluster in clusters:
        claims = [claims_by_id[cid] for cid in cluster.claim_ids if cid in claims_by_id]
        chunks = [chunks_by_id[cid] for cid in cluster.chunk_ids if cid in chunks_by_id]
        related_names = _related_topic_names(all_active, cluster)
        related_links = [topic_wikilink(name, hierarchy_enabled=False) for name in related_names]
        template_body = _render_topic_page(
            title=cluster.name,
            summary=cluster.summary or "",
            claims=claims,
            chunks=chunks,
            source_ids=list(cluster.source_ids),
            source_titles=source_titles,
            related_links=related_links,
            kb_id=kb_id,
        )
        page_name = topic_page_name(cluster.name)
        page_path = wiki_root / f"{page_name}.md"
        old_body = page_path.read_text(encoding="utf-8") if page_path.is_file() else ""

        content = template_body
        if use_llm:
            merged = _try_llm_merge(
                llm_client=llm_client,
                topic_name=cluster.name,
                old_body=old_body,
                template_body=template_body,
                claims=claims,
                chunks=chunks,
                source_ids=list(cluster.source_ids),
                source_titles=source_titles,
                related_links=related_links,
            )
            if merged is not None:
                content = merged
            else:
                logger.info("Wiki 主题页 LLM 失败，回退模板 topic=%s", cluster.name)

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

    index_topics = sorted({c.name for c in all_active} | set(topic_names))
    _upsert_index_topics(wiki_root, kb_id, index_topics)
    save_pages_meta(wiki_root, pages_meta)

    return CompileReport(pages_written=written, topics=topic_names)


def _compile_source_plan_for_source(
    knowledge: KnowledgePort,
    kb_id: str,
    source_id: str,
    wiki_root: Path,
    settings: Any,
    llm_client: Any = None,
) -> CompileReport:
    written, topics = compile_source_wiki_for_source(
        knowledge,
        kb_id,
        source_id,
        wiki_root,
        settings,
        llm_client=llm_client,
    )
    return CompileReport(pages_written=written, topics=topics)


def compile_topics_for_source(
    knowledge: KnowledgePort,
    kb_id: str,
    source_id: str,
    data_root: str | Path,
    settings: Any,
    graph: Any = None,
    llm_client: Any = None,
) -> CompileReport:
    """Compile topic pages for topics touched by ``source_id`` (template + optional LLM merge)."""
    del graph  # reserved for future cluster rebuild hook

    wiki_root = compile_wiki_root(data_root, kb_id)
    wiki_root.mkdir(parents=True, exist_ok=True)

    if getattr(settings, "wiki_hierarchy", False) and getattr(settings, "wiki_source_plan", True):
        return _compile_source_plan_for_source(
            knowledge, kb_id, source_id, wiki_root, settings, llm_client=llm_client
        )
    if getattr(settings, "wiki_hierarchy", False):
        return _compile_hierarchy_for_source(knowledge, kb_id, source_id, wiki_root, settings, llm_client=llm_client)
    return _compile_flat_for_source(knowledge, kb_id, source_id, wiki_root, settings, llm_client=llm_client)
