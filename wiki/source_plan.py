"""Source-centric wiki compilation: LLM plans pages from full source documents."""

from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from knowledge.models import Claim, SourceChunk
from knowledge.ports import KnowledgePort
from wiki.links import (
    chunk_wikilink,
    entity_wikilink,
    source_wikilink,
    wiki_page_path,
)
from wiki.meta import WikiPageMeta, load_pages_meta, save_pages_meta
from wiki.prompts import build_source_wiki_plan_prompt
from wiki.related import (
    build_wiki_catalog,
    ensure_related_topics_section,
    refresh_all_wiki_related_links,
    suggest_related_wiki_links,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SourceWikiPagePlan:
    folder: str
    slug: str
    title: str
    markdown: str


def infer_source_layout(source_id: str, source_title: str) -> tuple[str, str]:
    """Derive wiki folder/slug from source id or title."""
    if "__" in source_id:
        folder, slug = source_id.split("__", 1)
        return folder, slug
    title = source_title
    if title.lower().endswith(".md"):
        title = title[:-3]
    return "未分类", title


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def extract_page_summary(markdown: str, *, max_len: int = 120) -> str:
    """Extract a short description from the ``## 摘要`` section of a wiki page."""
    if not markdown:
        return ""
    match = re.search(r"##\s*摘要\s*\n+(.*?)(?=\n##\s|\Z)", markdown, flags=re.DOTALL)
    if not match:
        # Fallback: first non-empty, non-heading, non-frontmatter line
        for line in markdown.splitlines():
            stripped = line.strip().lstrip(">").strip()
            if not stripped or stripped.startswith("---") or stripped.startswith("#"):
                continue
            if stripped.startswith("tags:") or stripped.startswith("type:") or stripped.startswith("kb_id:"):
                continue
            text = re.sub(r"\[\[([^|\]]+)(?:\|[^\]]+)?\]\]", r"\1", stripped)
            text = re.sub(r"\s+", " ", text).strip()
            if text:
                return text if len(text) <= max_len else text[: max_len - 1] + "…"
        return ""
    block = match.group(1).strip()
    lines: list[str] = []
    for line in block.splitlines():
        stripped = line.strip().lstrip(">").strip()
        if not stripped:
            if lines:
                break
            continue
        lines.append(stripped)
    text = re.sub(r"\[\[([^|\]]+)(?:\|[^\]]+)?\]\]", r"\1", " ".join(lines))
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return ""
    return text if len(text) <= max_len else text[: max_len - 1] + "…"


def _folder_description(titles: list[str], summaries: list[str], *, max_len: int = 100) -> str:
    """Build a short folder blurb from child page titles (preferred) or summaries."""
    del summaries  # page-level lines already carry detailed summaries
    if not titles:
        return ""
    if len(titles) == 1:
        return f"收录「{titles[0]}」。"
    preview = "、".join(titles[:5])
    if len(titles) > 5:
        preview += f"等{len(titles)}篇"
    text = f"涵盖{preview}。"
    return text if len(text) <= max_len else text[: max_len - 1] + "…"


def _strip_json_fence(content: str) -> str:
    stripped = content.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    return stripped.strip()


def _format_frontmatter(kb_id: str, page_type: str = "source_page") -> str:
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


def _build_evidence(
    *,
    source_id: str,
    source_title: str,
    chunks: list[SourceChunk],
    claims: list[Claim],
) -> dict[str, Any]:
    return {
        "source_id": source_id,
        "source_title": source_title,
        "chunks": [
            {
                "id": chunk.id,
                "chunk_index": chunk.chunk_index,
                "title": chunk.title,
                "summary": chunk.summary,
                "section_path": list(chunk.section_path or []),
                "topics": list(chunk.topics or []),
                "excerpt": (chunk.text or "")[:400],
            }
            for chunk in sorted(chunks, key=lambda item: (item.chunk_index,))
        ],
        "claims": [
            {
                "subject": claim.subject,
                "predicate": claim.predicate,
                "object": claim.object,
                "source_ids": list(claim.source_ids),
            }
            for claim in sorted(claims, key=lambda item: (item.predicate, item.object))
        ],
    }


def _required_links(
    *,
    source_id: str,
    source_title: str,
    chunks: list[SourceChunk],
    claims: list[Claim],
) -> list[str]:
    links = [source_wikilink(source_id, source_title)]
    for chunk in chunks:
        label = chunk.title or f"chunk-{chunk.chunk_index}"
        links.append(chunk_wikilink(source_id, chunk.chunk_index, label))
    for claim in claims:
        if claim.subject:
            links.append(entity_wikilink(claim.subject))
        if claim.object:
            links.append(entity_wikilink(claim.object))
    seen: set[str] = set()
    ordered: list[str] = []
    for link in links:
        if link not in seen:
            seen.add(link)
            ordered.append(link)
    return ordered


def _render_fallback_page(
    *,
    kb_id: str,
    title: str,
    source_id: str,
    source_title: str,
    chunks: list[SourceChunk],
    claims: list[Claim],
    related_links: list[str] | None = None,
) -> str:
    """Template page grouped by section_path when LLM is unavailable."""
    lines = [
        _format_frontmatter(kb_id),
        f"# {title}",
        "",
        "## 摘要",
    ]
    summaries = [chunk.summary for chunk in chunks if chunk.summary]
    if summaries:
        lines.append(f"> {'；'.join(dict.fromkeys(summaries))}")
    else:
        lines.append("")
    lines.append("")

    lines.append("## 问答")
    if not claims:
        lines.append("- （无 Claim）")
    else:
        for claim in claims:
            question = claim.predicate.strip() or claim.subject.strip() or "说明"
            answer = claim.object.strip() or claim.subject.strip()
            lines.append(f"### {question}")
            lines.append(f"- **答**：{answer}")
            lines.append(f"- **来源**：{source_wikilink(source_id, source_title)}")
            lines.append("")

    sections: dict[str, list[SourceChunk]] = {}
    for chunk in chunks:
        key = " / ".join(chunk.section_path) if chunk.section_path else "正文"
        sections.setdefault(key, []).append(chunk)
    if sections:
        lines.append("## 章节要点")
        for section_name, section_chunks in sorted(sections.items()):
            lines.append(f"### {section_name}")
            for chunk in section_chunks:
                excerpt = chunk.summary or chunk.text[:120]
                label = chunk.title or f"chunk-{chunk.chunk_index}"
                lines.append(f"- {chunk_wikilink(source_id, chunk.chunk_index, label)}: {excerpt}")
            lines.append("")

    lines.extend(["## Chunks"])
    if not chunks:
        lines.append("- （无 Chunk）")
    else:
        for chunk in sorted(chunks, key=lambda item: item.chunk_index):
            label = chunk.title or f"chunk-{chunk.chunk_index}"
            excerpt = chunk.summary or chunk.text[:120]
            lines.append(f"- {chunk_wikilink(source_id, chunk.chunk_index, label)}: {excerpt}")
    lines.append("")

    lines.extend(["## 相关原文"])
    lines.append(f"- {source_wikilink(source_id, source_title)}")
    lines.append("")

    lines.extend(["## 相关主题"])
    if related_links:
        for link in related_links:
            lines.append(f"- {link}")
    else:
        lines.append("- （无相关主题）")
    lines.append("")

    entities: set[str] = set()
    for claim in claims:
        if claim.subject:
            entities.add(claim.subject)
        if claim.object and len(claim.object) <= 40:
            entities.add(claim.object)
    lines.extend(["## 相关实体"])
    if not entities:
        lines.append("- （无相关实体）")
    else:
        for name in sorted(entities):
            lines.append(f"- {entity_wikilink(name)}")
    lines.append("")
    return "\n".join(lines)


def _parse_llm_plan(raw: str) -> list[SourceWikiPagePlan] | None:
    try:
        payload = json.loads(_strip_json_fence(raw))
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(payload, dict):
        return None
    pages_raw = payload.get("pages")
    if not isinstance(pages_raw, list) or not pages_raw:
        return None
    plans: list[SourceWikiPagePlan] = []
    for item in pages_raw:
        if not isinstance(item, dict):
            continue
        folder = str(item.get("folder") or "").strip()
        slug = str(item.get("slug") or "").strip()
        title = str(item.get("title") or slug or folder).strip()
        markdown = str(item.get("markdown") or "").strip()
        if not folder or not slug or not markdown:
            continue
        plans.append(SourceWikiPagePlan(folder=folder, slug=slug, title=title, markdown=markdown))
    return plans or None


def _llm_client_ready(settings: Any, llm_client: Any) -> bool:
    if not getattr(settings, "wiki_source_plan_llm", False):
        return False
    if llm_client is None:
        return False
    return bool(getattr(llm_client, "is_configured", False))


def _plan_with_llm(
    *,
    llm_client: Any,
    source_id: str,
    source_title: str,
    source_text: str,
    folder: str,
    default_slug: str,
    evidence: dict[str, Any],
    old_pages: list[dict[str, str]],
    required_links: list[str],
    wiki_catalog: list[dict[str, str]],
) -> list[SourceWikiPagePlan] | None:
    prompt = build_source_wiki_plan_prompt(
        source_id=source_id,
        source_title=source_title,
        source_text=source_text,
        folder=folder,
        default_slug=default_slug,
        evidence=evidence,
        old_pages=old_pages,
        required_wikilinks=required_links,
        wiki_catalog=wiki_catalog,
    )
    try:
        raw = llm_client.chat_completions([{"role": "user", "content": prompt}], temperature=0.2)
    except Exception:
        logger.exception("Wiki source plan LLM call failed for source %s", source_id)
        return None
    plans = _parse_llm_plan(raw)
    if plans is None:
        return None
    source_link = source_wikilink(source_id, source_title)
    for plan in plans:
        if source_link not in plan.markdown:
            return None
    return plans


def _collect_old_pages(
    wiki_root: Path,
    pages_meta: dict[str, WikiPageMeta],
    source_id: str,
) -> list[dict[str, str]]:
    old_pages: list[dict[str, str]] = []
    for page_id, meta in pages_meta.items():
        if source_id not in meta.source_ids:
            continue
        path = wiki_root / meta.path
        if not path.is_file():
            continue
        old_pages.append(
            {
                "page_id": page_id,
                "path": meta.path,
                "title": meta.title,
                "body": path.read_text(encoding="utf-8"),
            }
        )
    return old_pages


def _purge_stale_pages_for_source(
    wiki_root: Path,
    pages_meta: dict[str, WikiPageMeta],
    source_id: str,
    keep_page_ids: set[str],
) -> None:
    to_remove: list[str] = []
    for page_id, meta in pages_meta.items():
        if source_id not in meta.source_ids:
            continue
        if page_id in keep_page_ids:
            continue
        if len(meta.source_ids) > 1:
            continue
        to_remove.append(page_id)
    for page_id in to_remove:
        meta = pages_meta.pop(page_id, None)
        if meta is None:
            continue
        target = wiki_root / meta.path
        if target.is_file():
            target.unlink()
    _prune_empty_dirs(wiki_root)


def _prune_empty_dirs(wiki_root: Path) -> None:
    for path in sorted(wiki_root.rglob("*"), reverse=True):
        if not path.is_dir():
            continue
        if path.name == ".meta":
            continue
        try:
            next(path.iterdir())
        except StopIteration:
            path.rmdir()


def rebuild_wiki_index(wiki_root: Path, kb_id: str, pages_meta: dict[str, WikiPageMeta]) -> None:
    """Rebuild index.md grouped by folder, with page and folder descriptions."""
    folders: dict[str, list[tuple[str, str, str, str]]] = {}
    for page_id, meta in pages_meta.items():
        rel = Path(meta.path)
        if rel.name == "_index.md":
            continue
        folder = rel.parent.as_posix() if rel.parent.as_posix() != "." else "未分类"
        slug = rel.stem
        summary = (meta.summary or "").strip()
        if not summary:
            page_path = wiki_root / meta.path
            if page_path.is_file():
                summary = extract_page_summary(page_path.read_text(encoding="utf-8"))
                if summary:
                    meta.summary = summary
        folders.setdefault(folder, []).append((slug, meta.title or slug, page_id, summary))

    lines = ["## 主题"]
    if not folders:
        lines.append("- （无主题）")
    else:
        for folder in sorted(folders):
            entries = sorted(folders[folder], key=lambda item: item[0])
            titles = [title for _slug, title, _page_id, _summary in entries]
            summaries = [summary for _slug, _title, _page_id, summary in entries if summary]
            folder_blurb = _folder_description(titles, summaries)
            lines.append("")
            lines.append(f"### {folder}")
            if folder_blurb:
                lines.append(f"> {folder_blurb}")
            for _slug, title, page_id, summary in entries:
                if summary:
                    lines.append(f"- [[{page_id}|{title}]] — {summary}")
                else:
                    lines.append(f"- [[{page_id}|{title}]]")

    index_path = wiki_root / "index.md"
    existing = index_path.read_text(encoding="utf-8") if index_path.is_file() else ""
    topic_block = "\n".join(lines) + "\n"

    if "## 主题" in existing:
        before, _, rest = existing.partition("## 主题")
        if "\n## " in rest:
            _, after_marker, after = rest.partition("\n## ")
            del after_marker
            new_content = before.rstrip() + "\n\n" + topic_block + "\n## " + after.lstrip()
        else:
            new_content = before.rstrip() + "\n\n" + topic_block
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


def compile_source_wiki_for_source(
    knowledge: KnowledgePort,
    kb_id: str,
    source_id: str,
    wiki_root: Path,
    settings: Any,
    llm_client: Any = None,
) -> tuple[int, list[str]]:
    """Compile wiki page(s) for one source using LLM plan + extracted evidence."""
    source = knowledge.get_source(source_id)
    if source is None:
        return 0, []

    source_text = knowledge.get_source_text(source_id)
    if not source_text:
        return 0, []

    folder, default_slug = infer_source_layout(source_id, source.title)
    chunks = list(knowledge.list_chunks(source_id, status="active"))
    claims = list(knowledge.get_claims_for_source(source_id))
    evidence = _build_evidence(
        source_id=source_id,
        source_title=source.title,
        chunks=chunks,
        claims=claims,
    )
    required_links = _required_links(
        source_id=source_id,
        source_title=source.title,
        chunks=chunks,
        claims=claims,
    )

    pages_meta = load_pages_meta(wiki_root)
    old_pages = _collect_old_pages(wiki_root, pages_meta, source_id)
    current_page_id = wiki_page_path(folder, default_slug)
    wiki_catalog = build_wiki_catalog(pages_meta, exclude_page_ids={current_page_id})
    claim_terms = [claim.subject for claim in claims] + [claim.predicate for claim in claims]
    chunk_terms = [topic for chunk in chunks for topic in (chunk.topics or [])]
    related_links = suggest_related_wiki_links(
        page_id=current_page_id,
        title=default_slug,
        source_text=source_text,
        extra_terms=claim_terms + chunk_terms,
        pages_meta=pages_meta,
        max_related=int(getattr(settings, "wiki_max_related", 12) or 12),
    )

    plans: list[SourceWikiPagePlan] | None = None
    if _llm_client_ready(settings, llm_client):
        plans = _plan_with_llm(
            llm_client=llm_client,
            source_id=source_id,
            source_title=source.title,
            source_text=source_text,
            folder=folder,
            default_slug=default_slug,
            evidence=evidence,
            old_pages=old_pages,
            required_links=required_links,
            wiki_catalog=wiki_catalog,
        )

    if plans is None:
        fallback = _render_fallback_page(
            kb_id=kb_id,
            title=default_slug,
            source_id=source_id,
            source_title=source.title,
            chunks=chunks,
            claims=claims,
            related_links=related_links,
        )
        plans = [SourceWikiPagePlan(folder=folder, slug=default_slug, title=default_slug, markdown=fallback)]

    now = datetime.now(timezone.utc)
    keep_page_ids: set[str] = set()
    written = 0
    topic_names: list[str] = []

    for plan in plans:
        page_id = wiki_page_path(plan.folder, plan.slug)
        rel_path = f"{page_id}.md"
        page_path = wiki_root / rel_path
        page_path.parent.mkdir(parents=True, exist_ok=True)

        body = plan.markdown.strip()
        if not body.startswith("---"):
            body = _format_frontmatter(kb_id) + body
        page_related = suggest_related_wiki_links(
            page_id=page_id,
            title=plan.title,
            source_text=source_text,
            extra_terms=claim_terms + chunk_terms,
            pages_meta=pages_meta,
            max_related=int(getattr(settings, "wiki_max_related", 12) or 12),
        ) or related_links
        body = ensure_related_topics_section(body, page_related)
        page_path.write_text(body if body.endswith("\n") else body + "\n", encoding="utf-8")

        keep_page_ids.add(page_id)
        pages_meta[page_id] = WikiPageMeta(
            path=rel_path.replace("\\", "/"),
            title=plan.title,
            kind="source_page",
            content_hash=_content_hash(body),
            source_ids=[source_id],
            updated_at=now,
            hub=plan.folder,
            role="leaf",
            summary=extract_page_summary(body) or None,
        )
        written += 1
        topic_names.append(plan.title)

    _purge_stale_pages_for_source(wiki_root, pages_meta, source_id, keep_page_ids)
    if getattr(settings, "wiki_migrate_flat", True):
        for path in wiki_root.glob("topic-*.md"):
            if path.is_file():
                path.unlink()
    rebuild_wiki_index(wiki_root, kb_id, pages_meta)
    save_pages_meta(wiki_root, pages_meta)
    relink_wiki_pages(wiki_root, settings, kb_id=kb_id)
    return written, topic_names


def relink_wiki_pages(wiki_root: Path, settings: Any, *, kb_id: str | None = None) -> int:
    """Refresh cross-page related-topic links and rebuild index descriptions."""
    pages_meta = load_pages_meta(wiki_root)
    if not pages_meta:
        return 0
    updated = refresh_all_wiki_related_links(
        wiki_root,
        pages_meta,
        max_related=int(getattr(settings, "wiki_max_related", 12) or 12),
    )
    for _page_id, meta in pages_meta.items():
        page_path = wiki_root / meta.path
        if not page_path.is_file():
            continue
        summary = extract_page_summary(page_path.read_text(encoding="utf-8"))
        if summary:
            meta.summary = summary

    resolved_kb_id = kb_id
    if not resolved_kb_id:
        index_path = wiki_root / "index.md"
        if index_path.is_file():
            match = re.search(r"^kb_id:\s*(.+)$", index_path.read_text(encoding="utf-8"), flags=re.MULTILINE)
            if match:
                resolved_kb_id = match.group(1).strip()
    if not resolved_kb_id:
        resolved_kb_id = "kb"

    rebuild_wiki_index(wiki_root, resolved_kb_id, pages_meta)
    save_pages_meta(wiki_root, pages_meta)
    return updated
