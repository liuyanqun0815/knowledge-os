"""以源文档为中心的 Wiki 编译：LLM 规划页面。"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from akos.domain.models.knowledge import Claim, SourceChunk
from akos.domain.ports.knowledge import KnowledgePort
from akos.application.wiki.layout import resolve_wiki_layout
from akos.application.wiki.links import (
    chunk_wikilink,
    entity_wikilink,
    source_wikilink,
    wiki_page_path,
    wiki_page_wikilink,
)
from akos.application.wiki.meta import WikiPageMeta, load_pages_meta, save_pages_meta
from akos.application.wiki.prompts import (
    build_source_wiki_outline_prompt,
    build_source_wiki_page_prompt,
    build_source_wiki_plan_prompt,
)
from akos.application.wiki.related import (
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


def infer_source_layout(
    source_id: str,
    source_title: str,
    source_text: str = "",
) -> tuple[str, str]:
    """Derive wiki folder/slug from source id, title, and optional body text."""
    decision = resolve_wiki_layout(source_id, source_title, source_text)
    return decision.folder, decision.default_slug


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


_EVIDENCE_CLAIM_LIMIT = 48
_REQUIRED_ENTITY_LIMIT = 24


def _build_evidence(
    *,
    source_id: str,
    source_title: str,
    chunks: list[SourceChunk],
    claims: list[Claim],
) -> dict[str, Any]:
    # Cap claims so long manuals (100+ claims) still fit the wiki-plan prompt.
    ranked_claims = sorted(claims, key=_faq_claim_score, reverse=True)[:_EVIDENCE_CLAIM_LIMIT]
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
                "excerpt": (chunk.text or "")[:800],
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
            for claim in ranked_claims
        ],
        "claims_total": len(claims),
        "claims_truncated": len(claims) > _EVIDENCE_CLAIM_LIMIT,
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
    # Only require a few high-signal entity subjects; objects often bloat the prompt.
    entity_subjects: list[str] = []
    seen_subjects: set[str] = set()
    for claim in sorted(claims, key=_faq_claim_score, reverse=True):
        subject = (claim.subject or "").strip()
        if not subject or subject in seen_subjects:
            continue
        seen_subjects.add(subject)
        entity_subjects.append(subject)
        if len(entity_subjects) >= _REQUIRED_ENTITY_LIMIT:
            break
    for subject in entity_subjects:
        links.append(entity_wikilink(subject))
    seen: set[str] = set()
    ordered: list[str] = []
    for link in links:
        if link not in seen:
            seen.add(link)
            ordered.append(link)
    return ordered

_FAQ_MAX = 8
_FAQ_PRIORITY_KEYWORDS = (
    "额度",
    "利率",
    "年利率",
    "条件",
    "材料",
    "申请",
    "赎回",
    "退货",
    "换货",
    "期限",
    "费用",
    "风险",
    "业绩比较基准",
    "起点",
)


def _format_claim_question(claim: Claim) -> str:
    """Build a Q heading that always carries the product/subject name when present."""
    subject = (claim.subject or "").strip()
    predicate = (claim.predicate or "").strip()
    if subject and predicate:
        if predicate.startswith(subject):
            return predicate if predicate.endswith(("？", "?")) else f"{predicate}？"
        return f"{subject}：{predicate}"
    return predicate or subject or "说明"


def _faq_claim_score(claim: Claim) -> tuple[int, float, str]:
    predicate = (claim.predicate or "").strip()
    priority = sum(1 for kw in _FAQ_PRIORITY_KEYWORDS if kw in predicate)
    confidence = float(getattr(claim, "confidence", 0.0) or 0.0)
    return (priority, confidence, predicate)


def _select_faq_claims(claims: list[Claim], *, limit: int = _FAQ_MAX) -> list[Claim]:
    """Pick a small set of high-frequency claims for the FAQ section."""
    if not claims:
        return []
    ranked = sorted(claims, key=_faq_claim_score, reverse=True)
    selected: list[Claim] = []
    seen: set[tuple[str, str]] = set()
    for claim in ranked:
        key = ((claim.subject or "").strip(), (claim.predicate or "").strip())
        if key in seen:
            continue
        seen.add(key)
        selected.append(claim)
        if len(selected) >= limit:
            break
    return selected


def _claims_for_topic(claims: list[Claim], topic_title: str, blob: str = "") -> list[Claim]:
    """Prefer claims whose subject matches the topic; else claims mentioned in blob."""
    title = (topic_title or "").strip()
    if not title:
        return []
    matched = [
        claim
        for claim in claims
        if claim.subject
        and (claim.subject == title or title in claim.subject or claim.subject in title)
    ]
    if matched:
        return matched
    body = blob or ""
    return [claim for claim in claims if claim.subject and claim.subject in body]


def _chunk_topic_key(chunk: SourceChunk) -> str:
    topics = [t.strip() for t in (chunk.topics or []) if t and str(t).strip()]
    if topics:
        return topics[0]
    if chunk.section_path:
        return str(chunk.section_path[0]).strip() or "正文"
    title = (chunk.title or "").strip()
    return title or "正文"


def _cluster_chunks_by_topic(chunks: list[SourceChunk]) -> list[tuple[str, list[SourceChunk]]]:
    """Group chunks by topic/section for deterministic bundle fallback."""
    groups: dict[str, list[SourceChunk]] = {}
    order: list[str] = []
    for chunk in sorted(chunks, key=lambda item: item.chunk_index):
        key = _chunk_topic_key(chunk)
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(chunk)
    return [(key, groups[key]) for key in order]


def _extract_point_bullets(
    *,
    chunks: list[SourceChunk],
    claims: list[Claim],
    summary_hint: str = "",
    max_bullets: int = 12,
) -> list[str]:
    """Build denser 要点 bullets from chunk text / claim pairs, not only one-line summaries."""
    bullets: list[str] = []
    seen: set[str] = set()

    def _add(text: str) -> None:
        cleaned = re.sub(r"\s+", " ", (text or "").strip())
        if len(cleaned) < 8:
            return
        key = cleaned[:80]
        if key in seen:
            return
        seen.add(key)
        bullets.append(cleaned[:220])

    for chunk in sorted(chunks, key=lambda item: item.chunk_index):
        label = (chunk.title or "").strip()
        body = (chunk.text or "").strip()
        if body:
            # Prefer explicit list-like lines; otherwise sentence slices from excerpt.
            raw_lines = [ln.strip(" -\t") for ln in body.splitlines() if ln.strip()]
            useful = [ln for ln in raw_lines if len(ln) >= 8 and not ln.startswith("#")]
            if len(useful) >= 2:
                for ln in useful[:6]:
                    _add(f"{label}：{ln}" if label else ln)
            else:
                excerpt = body.replace("\n", " ")
                parts = re.split(r"(?<=[。；;])", excerpt)
                for part in parts:
                    if len(bullets) >= max_bullets:
                        break
                    _add(f"{label}：{part}" if label and part.strip() else part)
        elif chunk.summary:
            _add(f"{label}：{chunk.summary}" if label else chunk.summary)
        if len(bullets) >= max_bullets:
            break

    if len(bullets) < 4:
        for claim in _select_faq_claims(claims, limit=max_bullets):
            subject = (claim.subject or "").strip()
            predicate = (claim.predicate or "").strip()
            obj = (claim.object or "").strip()
            if subject and predicate and obj:
                _add(f"{subject}的{predicate}：{obj}")
            if len(bullets) >= max_bullets:
                break

    if not bullets and summary_hint.strip():
        for para in summary_hint.strip().splitlines():
            _add(para)
            if len(bullets) >= max_bullets:
                break

    return bullets[:max_bullets]


def _render_fallback_page(
    *,
    kb_id: str,
    title: str,
    source_id: str,
    source_title: str,
    chunks: list[SourceChunk],
    claims: list[Claim],
    related_links: list[str] | None = None,
    summary_hint: str = "",
) -> str:
    """Template page: summary + points + curated FAQ (not full claim dump)."""
    lines = [
        _format_frontmatter(kb_id),
        f"# {title}",
        "",
        "## 摘要",
    ]
    summaries = [chunk.summary for chunk in chunks if chunk.summary]
    if summaries:
        lines.append(f"> {'；'.join(dict.fromkeys(summaries))}")
    elif summary_hint.strip():
        hint = summary_hint.strip().replace("\n", " ")
        lines.append(f"> {hint[:240]}{'…' if len(hint) > 240 else ''}")
    else:
        lines.append("")
    lines.append("")

    lines.append("## 要点")
    point_bullets = _extract_point_bullets(
        chunks=chunks,
        claims=claims,
        summary_hint=summary_hint,
    )
    if point_bullets:
        for bullet in point_bullets:
            lines.append(f"- {bullet}")
    else:
        lines.append("- （暂无要点）")
    lines.append("")

    lines.append("## 常见问题")
    faq_claims = _select_faq_claims(claims, limit=_FAQ_MAX)
    if not faq_claims:
        lines.append("- （暂无高频问题）")
        lines.append("")
    else:
        for claim in faq_claims:
            question = _format_claim_question(claim)
            answer = claim.object.strip() or claim.subject.strip()
            lines.append(f"### {question}")
            lines.append(f"- **答**：{answer}")
            lines.append(f"- **来源**：{source_wikilink(source_id, source_title)}")
            lines.append("")

    lines.extend(["## 相关原文"])
    lines.append(f"- {source_wikilink(source_id, source_title)}")
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

    lines.extend(["## 相关主题"])
    if related_links:
        for link in related_links:
            lines.append(f"- {link}")
    else:
        lines.append("- （无相关主题）")
    lines.append("")

    entities: set[str] = set()
    for claim in faq_claims:
        if claim.subject:
            entities.add(claim.subject)
    lines.extend(["## 相关实体"])
    if not entities:
        lines.append("- （无相关实体）")
    else:
        for name in sorted(entities):
            lines.append(f"- {entity_wikilink(name)}")
    lines.append("")
    return "\n".join(lines)


def _render_bundle_fallback_plans(
    *,
    kb_id: str,
    folder: str,
    product_name: str,
    source_id: str,
    source_title: str,
    source_text: str,
    chunks: list[SourceChunk],
    claims: list[Claim],
    related_links: list[str] | None = None,
) -> list[SourceWikiPagePlan]:
    """Deterministic multi-page fallback: cluster by chunk topics, not rigid TOC."""
    del source_text  # available for future soft hints; clustering uses chunks
    clusters = _cluster_chunks_by_topic(chunks)
    # Prefer multi-topic clusters; if only one bucket, keep a single overview page.
    if len(clusters) < 2:
        return [
            SourceWikiPagePlan(
                folder=folder,
                slug="_index",
                title=product_name,
                markdown=_render_fallback_page(
                    kb_id=kb_id,
                    title=product_name,
                    source_id=source_id,
                    source_title=source_title,
                    chunks=chunks,
                    claims=claims,
                    related_links=related_links,
                ),
            )
        ]

    selected = clusters[:8]
    toc_lines = [wiki_page_wikilink(folder, title, title) for title, _group in selected]
    index_lines = [
        _format_frontmatter(kb_id),
        f"# {product_name}",
        "",
        "## 摘要",
        f"> 按主题整理为 {len(selected)} 个子页，详见目录。",
        "",
        "## 要点",
        "- 本页为总览；具体规则见各主题子页。",
        "",
        "## 主题目录",
        *[f"- {link}" for link in toc_lines],
        "",
        "## 常见问题",
        "- （详见各主题子页）",
        "",
        "## 相关原文",
        f"- {source_wikilink(source_id, source_title)}",
        "",
        "## 相关主题",
    ]
    if related_links:
        index_lines.extend(f"- {link}" for link in related_links)
    else:
        index_lines.append("- （无相关主题）")
    index_lines.append("")

    plans = [
        SourceWikiPagePlan(
            folder=folder,
            slug="_index",
            title=product_name,
            markdown="\n".join(index_lines),
        )
    ]
    for topic_title, topic_chunks in selected:
        blob = "\n".join((c.summary or c.text or "") for c in topic_chunks)
        topic_claims = _claims_for_topic(claims, topic_title, blob)
        plans.append(
            SourceWikiPagePlan(
                folder=folder,
                slug=topic_title,
                title=topic_title,
                markdown=_render_fallback_page(
                    kb_id=kb_id,
                    title=topic_title,
                    source_id=source_id,
                    source_title=source_title,
                    chunks=topic_chunks,
                    claims=topic_claims,
                    related_links=[wiki_page_wikilink(folder, "_index", product_name)]
                    + [link for link in toc_lines if topic_title not in link],
                    summary_hint=blob,
                ),
            )
        )
    return plans


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


def _parse_llm_outline(raw: str) -> list[dict[str, str]] | None:
    try:
        payload = json.loads(_strip_json_fence(raw))
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(payload, dict):
        return None
    pages_raw = payload.get("pages")
    if not isinstance(pages_raw, list) or not pages_raw:
        return None
    outline: list[dict[str, str]] = []
    for item in pages_raw:
        if not isinstance(item, dict):
            continue
        folder = str(item.get("folder") or "").strip()
        slug = str(item.get("slug") or "").strip()
        title = str(item.get("title") or slug or folder).strip()
        focus = str(item.get("focus") or title).strip()
        if not folder or not slug or not title:
            continue
        outline.append({"folder": folder, "slug": slug, "title": title, "focus": focus})
    return outline or None


def _parse_llm_page_markdown(raw: str) -> str | None:
    try:
        payload = json.loads(_strip_json_fence(raw))
    except (json.JSONDecodeError, TypeError):
        text = _strip_json_fence(raw).strip()
        return text if text.startswith("#") or text.startswith("##") else None
    if isinstance(payload, dict):
        markdown = str(payload.get("markdown") or "").strip()
        return markdown or None
    return None


def _focus_tokens(title: str, focus: str) -> list[str]:
    """从 title/focus 的 include 段提取用于匹配的关键词。"""
    text = focus or title
    if "include:" in text or "include：" in text:
        part = re.split(r"include[:：]", text, maxsplit=1)[-1]
        part = re.split(r"exclude[:：]", part, maxsplit=1)[0]
        text = part
    tokens: list[str] = []
    for token in re.split(r"\s+|、|；|;|/|，|,", f"{title} {text}"):
        token = token.strip()
        if len(token) >= 2 and token not in {"include", "exclude", "本页", "其他"}:
            tokens.append(token)
    return tokens


def _chunk_window(all_chunks: list[dict[str, Any]], *, title: str, page_index: int) -> list[dict[str, Any]]:
    """无强匹配时按页序分窗，避免每页都落到相同的前几条 chunk。"""
    if not all_chunks:
        return []
    width = max(2, min(4, len(all_chunks) // max(page_index + 1, 1)))
    start = min(page_index * width, max(0, len(all_chunks) - width))
    return all_chunks[start : start + width]


def _evidence_for_page(
    evidence: dict[str, Any],
    *,
    title: str,
    focus: str,
    page_index: int = 0,
) -> dict[str, Any]:
    """Narrow evidence to chunks/claims likely relevant to one page."""
    needle_tokens = _focus_tokens(title, focus)
    all_chunks = list(evidence.get("chunks") or [])
    chunks: list[dict[str, Any]] = []
    for chunk in all_chunks:
        blob = " ".join(
            [
                str(chunk.get("title") or ""),
                " ".join(chunk.get("topics") or []),
                str(chunk.get("summary") or ""),
                str(chunk.get("excerpt") or ""),
            ]
        ).lower()
        if title in str(chunk.get("title") or "") or any(
            title in str(t) for t in (chunk.get("topics") or [])
        ):
            chunks.append(chunk)
            continue
        if any(token.lower() in blob for token in needle_tokens):
            chunks.append(chunk)
    if not chunks:
        chunks = _chunk_window(all_chunks, title=title, page_index=page_index)

    all_claims = list(evidence.get("claims") or [])
    claims: list[dict[str, Any]] = []
    for claim in all_claims:
        subject = str(claim.get("subject") or "")
        predicate = str(claim.get("predicate") or "")
        obj = str(claim.get("object") or "")
        blob = f"{subject}{predicate}{obj}"
        if title in subject or subject in title:
            claims.append(claim)
            continue
        if any(token in blob for token in needle_tokens):
            claims.append(claim)
    if not claims and all_claims:
        start = (page_index * 6) % len(all_claims)
        claims = all_claims[start : start + 6]

    return {
        "source_id": evidence.get("source_id"),
        "source_title": evidence.get("source_title"),
        "chunks": chunks[:6],
        "claims": claims[:12],
    }


def _source_text_for_page(
    page_evidence: dict[str, Any],
    source_text: str,
    *,
    slug: str,
    max_chars: int = 7000,
) -> str:
    """撰写单页时尽量只给相关 excerpt，降低跨页重复。"""
    if slug == "_index":
        return source_text[: min(1200, len(source_text))]

    parts: list[str] = []
    for chunk in page_evidence.get("chunks") or []:
        excerpt = str(chunk.get("excerpt") or "").strip()
        if excerpt:
            title = str(chunk.get("title") or "").strip()
            header = f"### {title}\n" if title else ""
            parts.append(f"{header}{excerpt}")
    if parts:
        joined = "\n\n".join(parts)
        return joined[:max_chars]
    return source_text[:max_chars]


def _sibling_scope_hint(outline: list[dict[str, str]], *, slug: str) -> str:
    lines: list[str] = []
    for item in outline:
        if item.get("slug") == slug:
            continue
        focus = str(item.get("focus") or item.get("title") or "").strip()
        lines.append(f"- [[{item.get('folder', '')}/{item.get('slug', '')}|{item.get('title', '')}]]：{focus}")
    return "\n".join(lines) if lines else ""


def _wiki_source_plan_uses_llm(settings: Any, llm_client: Any) -> bool:
    if not getattr(settings, "wiki_compile", False):
        return False
    from akos.adapters.llm.client import require_llm_configured

    require_llm_configured(llm_client, feature="Wiki 源文档规划")
    return True


def _normalize_plan_folder(
    plan_folder: str,
    *,
    folder: str,
    category: str,
    split_mode: str,
) -> str:
    normalized = (plan_folder or "").strip() or folder
    if normalized in {"", "未分类"}:
        normalized = folder
    if split_mode in {"product_bundle", "catalog_bundle"}:
        if normalized == category or not normalized.startswith(f"{category}/"):
            normalized = folder
    return normalized


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
    split_mode: str = "single",
    category: str = "",
    product_name: str = "",
) -> list[SourceWikiPagePlan] | None:
    source_link = source_wikilink(source_id, source_title)
    # Short docs: keep one-shot. Long bundles: outline then write pages one-by-one
    # to avoid truncated multi-page JSON.
    if split_mode == "single":
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
            split_mode=split_mode,
            category=category,
            product_name=product_name,
        )
        raw = llm_client.chat_completions([{"role": "user", "content": prompt}], temperature=0.2)
        plans = _parse_llm_plan(raw)
        if plans is None:
            return None
        normalized: list[SourceWikiPagePlan] = []
        for plan in plans:
            if source_link not in plan.markdown:
                return None
            normalized.append(
                SourceWikiPagePlan(
                    folder=_normalize_plan_folder(
                        plan.folder, folder=folder, category=category, split_mode=split_mode
                    ),
                    slug=plan.slug,
                    title=plan.title,
                    markdown=plan.markdown,
                )
            )
        return normalized or None

    outline_prompt = build_source_wiki_outline_prompt(
        source_id=source_id,
        source_title=source_title,
        source_text=source_text,
        folder=folder,
        default_slug=default_slug,
        evidence=evidence,
        split_mode=split_mode,
        category=category,
        product_name=product_name,
    )
    outline_raw = llm_client.chat_completions(
        [{"role": "user", "content": outline_prompt}],
        temperature=0.2,
        timeout=90.0,
    )
    outline = _parse_llm_outline(outline_raw)
    if outline is None or len(outline) < 2:
        return None

    # Keep prompt volume bounded for long manuals.
    outline = outline[:10]
    for item in outline:
        item["folder"] = _normalize_plan_folder(
            item["folder"], folder=folder, category=category, split_mode=split_mode
        )

    page_required = [source_link] + [
        link for link in required_links if link.startswith("[[chunk-")
    ][:8]
    plans: list[SourceWikiPagePlan] = []
    for page_index, item in enumerate(outline):
        page_evidence = _evidence_for_page(
            evidence,
            title=item["title"],
            focus=item["focus"],
            page_index=page_index,
        )
        page_source_text = _source_text_for_page(
            page_evidence,
            source_text,
            slug=item["slug"],
        )
        page_prompt = build_source_wiki_page_prompt(
            source_id=source_id,
            source_title=source_title,
            source_text=page_source_text,
            folder=item["folder"],
            slug=item["slug"],
            title=item["title"],
            focus=item["focus"],
            evidence=page_evidence,
            required_wikilinks=page_required,
            sibling_pages=outline,
            product_name=product_name,
            sibling_scope_hint=_sibling_scope_hint(outline, slug=item["slug"]),
        )
        page_raw = llm_client.chat_completions(
            [{"role": "user", "content": page_prompt}],
            temperature=0.2,
            timeout=90.0,
        )
        markdown = _parse_llm_page_markdown(page_raw)
        if not markdown or source_link not in markdown:
            return None
        if "## 要点" not in markdown:
            return None
        plans.append(
            SourceWikiPagePlan(
                folder=item["folder"],
                slug=item["slug"],
                title=item["title"],
                markdown=markdown,
            )
        )
    if len(plans) < 2:
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
        if rel.parent.as_posix() != ".":
            folder = rel.parent.as_posix()
        else:
            folder = "未分类"
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
            entries = sorted(
                folders[folder],
                key=lambda item: (0 if item[0] == "_index" else 1, item[0]),
            )
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

    chunks = list(knowledge.list_chunks(source_id, status="active"))
    claims = list(knowledge.get_claims_for_source(source_id))
    subject_count = len({claim.subject for claim in claims})
    min_chars = int(getattr(settings, "wiki_split_min_chars", 5000) or 5000)
    layout = resolve_wiki_layout(
        source_id,
        source.title,
        source_text,
        chunk_count=len(chunks),
        claim_subject_count=subject_count,
        min_chars=min_chars,
    )
    folder = layout.folder
    default_slug = layout.default_slug
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
        title=layout.product_name or default_slug,
        source_text=source_text,
        extra_terms=claim_terms + chunk_terms,
        pages_meta=pages_meta,
        max_related=int(getattr(settings, "wiki_max_related", 12) or 12),
    )

    from akos.adapters.llm.client import LlmCallError

    plans: list[SourceWikiPagePlan] | None = None
    if _wiki_source_plan_uses_llm(settings, llm_client):
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
            split_mode=layout.split_mode,
            category=layout.category,
            product_name=layout.product_name,
        )
        if plans is None:
            raise LlmCallError(f"Wiki 源文档规划未产生有效页面 source={source_id}")

    if plans is None:
        if layout.split_mode in {"catalog_bundle", "product_bundle"}:
            plans = _render_bundle_fallback_plans(
                kb_id=kb_id,
                folder=folder,
                product_name=layout.product_name or default_slug,
                source_id=source_id,
                source_title=source.title,
                source_text=source_text,
                chunks=chunks,
                claims=claims,
                related_links=related_links,
            )
        else:
            fallback = _render_fallback_page(
                kb_id=kb_id,
                title=layout.product_name or default_slug,
                source_id=source_id,
                source_title=source.title,
                chunks=chunks,
                claims=claims,
                related_links=related_links,
            )
            plans = [
                SourceWikiPagePlan(
                    folder=folder,
                    slug=default_slug,
                    title=layout.product_name or default_slug,
                    markdown=fallback,
                )
            ]

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
