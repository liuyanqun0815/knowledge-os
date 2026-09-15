from __future__ import annotations

import re
from pathlib import Path

from retrieval.ports import Hit
from retrieval.wiki_keywords import extract_keywords

_WIKI_TOP_K_CAP = 5
_INDEX_ENTRY_RE = re.compile(
    r"- \[\[([^\]|#]+)(?:\|([^\]]+))?\]\]\s*(?:—|-)?\s*(.*)$"
)
_WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:\|[^\]]+)?\]\]")


def _excerpt(text: str, limit: int = 160) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1] + "…"


def _title_from_markdown(text: str) -> str | None:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip() or None
    return None


def _keyword_count(keywords: list[str], haystack: str) -> int:
    if not keywords or not haystack:
        return 0
    return sum(1 for kw in keywords if kw and kw in haystack)


def _expand_one_hop(root: Path, text: str) -> list[str]:
    neighbors: list[str] = []
    for match in _WIKILINK_RE.finditer(text):
        target = match.group(1).strip().replace("\\", "/")
        if target.startswith(("source-", "chunk-")):
            continue
        if (root / f"{target}.md").is_file():
            neighbors.append(target)
    return neighbors


def _parse_index_entries(index_text: str) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    for line in index_text.splitlines():
        match = _INDEX_ENTRY_RE.match(line.strip())
        if not match:
            continue
        path = match.group(1).strip().replace("\\", "/")
        title = (match.group(2) or path.split("/")[-1]).strip()
        blurb = (match.group(3) or "").strip()
        entries.append({"path": path, "title": title, "blurb": blurb})
    return entries


def _page_rel_id(root: Path, file_path: Path) -> str:
    return file_path.relative_to(root).as_posix().removesuffix(".md")


def _score_candidates(
    root: Path,
    keywords: list[str],
    candidate_rels: list[str],
) -> list[Hit]:
    scored: list[tuple[float, Hit]] = []
    for rel in candidate_rels:
        file_path = root / f"{rel}.md"
        try:
            text = file_path.read_text(encoding="utf-8") if file_path.is_file() else None
        except OSError:
            text = None
        if text is None:
            continue
        title = _title_from_markdown(text) or rel.split("/")[-1]
        path = f"{rel}.md"
        title_hits = _keyword_count(keywords, f"{rel} {title}")
        body_hits = _keyword_count(keywords, text)
        raw = 2 * title_hits + body_hits
        if raw <= 0:
            continue
        hit = Hit(
            score=float(raw),
            snippet=_excerpt(text),
            hit_type="wiki",
            ref_id=rel,
            title=title,
            path=path,
        )
        scored.append((float(raw), hit))
    if not scored:
        return []
    max_raw = max(raw for raw, _ in scored)
    hits = []
    for raw, hit in scored:
        hit.score = raw / max_raw if max_raw else 0.0
        hits.append(hit)
    hits.sort(key=lambda item: item.score, reverse=True)
    return hits


class WikiPageRetrieval:
    """Index-routed wiki retrieval (on-disk reads; no body cache)."""

    def __init__(self, llm_client=None) -> None:
        self._wiki_root: Path | None = None
        self._llm_client = llm_client

    def index_wiki_root(self, root: str | Path) -> None:
        self._wiki_root = Path(root)

    def _leaf_pages(self) -> list[Path]:
        root = self._wiki_root
        if root is None or not root.is_dir():
            return []
        pages: list[Path] = []
        for path in root.rglob("*.md"):
            if ".meta" in path.parts:
                continue
            if path.name in {"index.md", "log.md"}:
                continue
            pages.append(path)
        return pages

    def _read_text(self, path: Path) -> str | None:
        try:
            return path.read_text(encoding="utf-8")
        except OSError:
            return None

    def search(self, query: str, top_k: int = 5) -> list[Hit]:
        limit = min(max(top_k, 0), _WIKI_TOP_K_CAP)
        if limit <= 0:
            return []
        root = self._wiki_root
        if root is None or not root.is_dir():
            return []
        leaves = self._leaf_pages()
        if not leaves:
            return []
        index_path = root / "index.md"
        index_text = self._read_text(index_path)
        if not index_text:
            return []
        keywords = extract_keywords(query)
        entries = _parse_index_entries(index_text)
        seeds: list[str] = []
        for entry in entries:
            hay = f"{entry['path']} {entry['title']} {entry['blurb']}"
            if _keyword_count(keywords, hay) > 0:
                seeds.append(entry["path"])
        if seeds:
            candidates: list[str] = []
            for seed in seeds:
                if seed not in candidates:
                    candidates.append(seed)
                seed_file = root / f"{seed}.md"
                seed_text = self._read_text(seed_file)
                if not seed_text:
                    continue
                for neighbor in _expand_one_hop(root, seed_text):
                    if neighbor not in candidates:
                        candidates.append(neighbor)
        else:
            candidates = [_page_rel_id(root, path) for path in leaves]
        hits = _score_candidates(root, keywords, candidates)
        if hits:
            return hits[:limit]
        return []
