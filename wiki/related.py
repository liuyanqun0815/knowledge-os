"""Cross-page wikilink suggestions and injection for compiled wiki pages."""

from __future__ import annotations

import re
from pathlib import Path

from wiki.links import wiki_page_wikilink
from wiki.meta import WikiPageMeta

_TERM_PATTERN = re.compile(r"[\u4e00-\u9fff]{2,}|[a-zA-Z0-9]{2,}")
_RELATED_SECTION = "## 相关主题"
_RELATED_HINTS: dict[str, list[str]] = {
    "尺码选择指南": ["七天无理由退货", "不予退换货情形", "退换货流程"],
    "七天无理由退货": ["尺码选择指南", "退换货流程", "退款到账时效", "不予退换货情形", "质量问题退换货"],
    "退换货流程": ["七天无理由退货", "退款到账时效", "不予退换货情形", "质量问题退换货"],
    "退款到账时效": ["七天无理由退货", "退换货流程", "订单取消规则"],
    "质量问题退换货": ["七天无理由退货", "退换货流程", "不予退换货情形"],
    "不予退换货情形": ["七天无理由退货", "尺码选择指南", "退换货流程"],
    "商品真伪与正品保障": ["商品保养说明", "促销活动规则"],
    "发货时效说明": ["物流查询指引", "签收与拒收"],
    "物流查询指引": ["发货时效说明", "签收与拒收"],
    "签收与拒收": ["物流查询指引", "发货时效说明", "退换货流程"],
    "会员权益说明": ["促销活动规则", "优惠券使用规则"],
    "促销活动规则": ["会员权益说明", "优惠券使用规则"],
    "优惠券使用规则": ["促销活动规则", "会员权益说明", "订单取消规则"],
}


def _terms(*texts: str) -> set[str]:
    terms: set[str] = set()
    for text in texts:
        if not text:
            continue
        terms.update(_TERM_PATTERN.findall(text))
    return terms


def build_wiki_catalog(
    pages_meta: dict[str, WikiPageMeta],
    *,
    exclude_page_ids: set[str] | None = None,
) -> list[dict[str, str]]:
    excluded = exclude_page_ids or set()
    catalog: list[dict[str, str]] = []
    for page_id, meta in sorted(pages_meta.items()):
        if page_id in excluded:
            continue
        if meta.kind not in {"source_page", "topic", "leaf", "hub"}:
            continue
        if meta.path.endswith("_index.md"):
            continue
        rel = Path(meta.path)
        folder = rel.parent.as_posix() if rel.parent.as_posix() != "." else (meta.hub or "未分类")
        slug = rel.stem
        catalog.append(
            {
                "page_id": page_id,
                "folder": folder,
                "slug": slug,
                "title": meta.title or slug,
            }
        )
    return catalog


def suggest_related_wiki_links(
    *,
    page_id: str,
    title: str,
    source_text: str,
    extra_terms: list[str] | None = None,
    pages_meta: dict[str, WikiPageMeta],
    max_related: int = 8,
) -> list[str]:
    """Score other wiki pages and return wikilink strings."""
    current_terms = _terms(title, source_text, *(extra_terms or []))
    rel = Path(pages_meta[page_id].path) if page_id in pages_meta else None
    if rel is not None:
        current_terms.update(_terms(rel.stem, rel.parent.as_posix()))

    scored: list[tuple[int, str, str, str]] = []
    for other_id, meta in pages_meta.items():
        if other_id == page_id:
            continue
        if meta.path.endswith("_index.md"):
            continue
        other_rel = Path(meta.path)
        other_folder = other_rel.parent.as_posix() if other_rel.parent.as_posix() != "." else (meta.hub or "未分类")
        other_slug = other_rel.stem
        other_title = meta.title or other_slug
        other_terms = _terms(other_title, other_slug, other_folder, other_id.replace("/", " "))
        overlap = len(current_terms & other_terms)
        hint_boost = 0
        for hint_title in _RELATED_HINTS.get(title, []):
            if hint_title in other_title or hint_title in other_slug:
                hint_boost += 3
        for hint_title in _RELATED_HINTS.get(other_slug, []):
            if title in hint_title or title in other_slug:
                hint_boost += 1
        score = overlap + hint_boost
        if score <= 0:
            continue
        scored.append((score, other_folder, other_slug, other_title))

    scored.sort(key=lambda item: (-item[0], item[3]))
    links: list[str] = []
    seen: set[str] = set()
    for _score, folder, slug, other_title in scored[: max(0, max_related)]:
        link = wiki_page_wikilink(folder, slug, other_title)
        if link in seen:
            continue
        seen.add(link)
        links.append(link)
    return links


def ensure_related_topics_section(markdown: str, related_links: list[str]) -> str:
    """Ensure page contains a related-topics section with cross-page wikilinks."""
    if not related_links:
        return markdown

    section_lines = [_RELATED_SECTION]
    for link in related_links:
        section_lines.append(f"- {link}")
    new_section = "\n".join(section_lines) + "\n"

    if _RELATED_SECTION in markdown:
        before, _, rest = markdown.partition(_RELATED_SECTION)
        if "\n## " in rest:
            _, after = rest.split("\n## ", 1)
            tail = "\n## " + after
        else:
            tail = ""
        return before.rstrip() + "\n\n" + new_section + tail

    insert_before = ("## Chunks", "## 关键词", "## 相关实体", "## 相关原文")
    for marker in insert_before:
        if marker in markdown:
            return markdown.replace(marker, new_section + "\n" + marker, 1)
    return markdown.rstrip() + "\n\n" + new_section


def refresh_all_wiki_related_links(
    wiki_root: Path,
    pages_meta: dict[str, WikiPageMeta],
    *,
    max_related: int = 8,
) -> int:
    """Recompute related-topic sections for every wiki page."""
    updated = 0
    for page_id, meta in list(pages_meta.items()):
        if meta.path.endswith("_index.md"):
            continue
        file_path = wiki_root / meta.path
        if not file_path.is_file():
            continue
        body = file_path.read_text(encoding="utf-8")
        related = suggest_related_wiki_links(
            page_id=page_id,
            title=meta.title,
            source_text=body,
            pages_meta=pages_meta,
            max_related=max_related,
        )
        new_body = ensure_related_topics_section(body, related)
        if new_body != body:
            file_path.write_text(new_body if new_body.endswith("\n") else new_body + "\n", encoding="utf-8")
            updated += 1
    return updated
