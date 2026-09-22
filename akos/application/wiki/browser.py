from __future__ import annotations

import re
from pathlib import Path

from akos.application.wiki.meta import WikiPageMeta, load_pages_meta

_SNIPPET_RADIUS = 40
_RANK_TITLE = 3
_RANK_SUMMARY = 2
_RANK_BODY = 1


def resolve_wiki_page_path(wiki_root: Path, page_id: str) -> Path:
    root = wiki_root.resolve()
    raw = "index.md" if page_id in {"", "index"} else f"{page_id}.md"
    target = (root / raw).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        raise ValueError("path_escape") from None
    if not target.is_file():
        raise FileNotFoundError(page_id)
    return target


def _parse_hub_descriptions(index_md: str) -> dict[str, str]:
    descriptions: dict[str, str] = {}
    lines = index_md.splitlines()
    hub_name: str | None = None
    for line in lines:
        heading = re.match(r"^###\s+(.+?)\s*$", line)
        if heading:
            hub_name = heading.group(1).strip()
            continue
        if hub_name and line.startswith(">"):
            descriptions[hub_name] = line.lstrip(">").strip()
            hub_name = None
    return descriptions


def _first_h1_title(markdown: str) -> str | None:
    for line in markdown.splitlines():
        match = re.match(r"^#\s+(.+?)\s*$", line)
        if match:
            title = match.group(1).strip()
            if title:
                return title
    return None


def build_wiki_tree(wiki_root: Path) -> dict:
    pages_meta = load_pages_meta(wiki_root)
    hub_descriptions: dict[str, str] = {}
    index_path = wiki_root / "index.md"
    index_text: str | None = None
    if index_path.is_file():
        index_text = index_path.read_text(encoding="utf-8")
        hub_descriptions = _parse_hub_descriptions(index_text)

    def _sort_pages(pages: list[dict]) -> list[dict]:
        return sorted(
            pages,
            key=lambda item: (0 if str(item["page_id"]).endswith("/_index") else 1, item["title"] or ""),
        )

    def _page_entry(page_id: str, meta: WikiPageMeta) -> dict:
        return {
            "page_id": page_id,
            "title": meta.title,
            "summary": meta.summary,
        }

    category_pages: dict[str, list[dict]] = {}
    category_products: dict[str, dict[str, list[dict]]] = {}

    for page_id, meta in pages_meta.items():
        entry = _page_entry(page_id, meta)
        parts = page_id.split("/")
        if len(parts) <= 2:
            category = parts[0] if len(parts) == 2 else (meta.hub or "其他")
            category_pages.setdefault(category, []).append(entry)
            continue
        category, product = parts[0], parts[1]
        category_products.setdefault(category, {}).setdefault(product, []).append(entry)

    hub_items = []
    if index_text is not None:
        hub_items.append(
            {
                "name": "总览",
                "description": None,
                "pages": [
                    {
                        "page_id": "index",
                        "title": "综合概览",
                        "summary": None,
                    }
                ],
                "groups": [],
            }
        )

    for category in sorted(set(category_pages) | set(category_products)):
        if category == "总览":
            continue
        groups: list[dict] = []
        for product_slug in sorted(category_products.get(category, {})):
            product_pages = _sort_pages(category_products[category][product_slug])
            display_name = product_slug
            for page in product_pages:
                if str(page["page_id"]).endswith("/_index"):
                    display_name = page["title"] or product_slug
                    break
            groups.append({"name": display_name, "pages": product_pages})
        hub_items.append(
            {
                "name": category,
                "description": hub_descriptions.get(category),
                "pages": _sort_pages(category_pages.get(category, [])),
                "groups": groups,
            }
        )
    return {"hubs": hub_items}


def read_wiki_page(wiki_root: Path, page_id: str) -> dict:
    path = resolve_wiki_page_path(wiki_root, page_id)
    markdown = path.read_text(encoding="utf-8")
    meta = load_pages_meta(wiki_root).get(page_id)
    if page_id in {"", "index"}:
        title = "综合概览"
    elif meta:
        title = meta.title
    else:
        title = _first_h1_title(markdown) or path.stem
    normalized_page_id = page_id if page_id else "index"
    root = wiki_root.resolve()
    rel_path = str(path.relative_to(root)).replace("\\", "/")
    return {
        "page_id": normalized_page_id,
        "title": title,
        "path": rel_path,
        "markdown": markdown,
    }


def _extract_snippet(text: str, needle: str) -> str | None:
    if not text or not needle:
        return None
    lowered = text.casefold()
    idx = lowered.find(needle.casefold())
    if idx < 0:
        return None
    start = max(0, idx - _SNIPPET_RADIUS)
    end = min(len(text), idx + len(needle) + _SNIPPET_RADIUS)
    snippet = text[start:end]
    if start > 0:
        snippet = f"…{snippet}"
    if end < len(text):
        snippet = f"{snippet}…"
    return snippet


def _page_body(wiki_root: Path, meta: WikiPageMeta) -> str:
    page_path = wiki_root / meta.path
    if page_path.is_file():
        return page_path.read_text(encoding="utf-8")
    return ""


def _search_page(
    wiki_root: Path,
    page_id: str,
    meta: WikiPageMeta,
    needle: str,
) -> tuple[int, dict] | None:
    title = meta.title or ""
    summary = meta.summary or ""
    body = _page_body(wiki_root, meta)

    rank = 0
    snippets: list[str] = []
    for field_rank, text in (
        (_RANK_TITLE, title),
        (_RANK_SUMMARY, summary),
        (_RANK_BODY, body),
    ):
        if needle.casefold() not in text.casefold():
            continue
        rank = max(rank, field_rank)
        snippet = _extract_snippet(text, needle)
        if snippet and snippet not in snippets:
            snippets.append(snippet)

    if rank == 0:
        return None
    return rank, {"page_id": page_id, "title": title, "snippets": snippets}


def search_wiki_pages(wiki_root: Path, query: str, *, limit: int = 50) -> dict:
    if not query.strip():
        return {"query": query, "total": 0, "hits": []}

    needle = query.strip()
    pages_meta = load_pages_meta(wiki_root)
    scored: list[tuple[int, str, dict]] = []
    for page_id, meta in pages_meta.items():
        match = _search_page(wiki_root, page_id, meta, needle)
        if match is None:
            continue
        rank, hit = match
        scored.append((rank, meta.title or page_id, hit))

    scored.sort(key=lambda item: (-item[0], item[1]))
    effective_limit = max(1, min(limit, 100))
    hits = [item[2] for item in scored[:effective_limit]]
    return {"query": query, "total": len(scored), "hits": hits}
