from __future__ import annotations

import json
import re
from pathlib import Path

from retrieval.ports import Hit
from retrieval.wiki_keywords import extract_keywords

_WIKI_TOP_K_CAP = 5
_INDEX_ENTRY_RE = re.compile(
    r"- \[\[([^\]|#]+)(?:\|([^\]]+))?\]\]\s*(?:—|-)?\s*(.*)$"
)
_WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:\|[^\]]+)?\]\]")
_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)
_SKIP_PAGE_NAMES = frozenset({"index", "log"})


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


def _normalize_rel(rel: str) -> str:
    return rel.strip().replace("\\", "/").removesuffix(".md").lstrip("/")


def _is_blocked_rel(rel: str) -> bool:
    if not rel:
        return True
    if rel.startswith(("source-", "chunk-")):
        return True
    name = Path(rel).name
    if name in _SKIP_PAGE_NAMES:
        return True
    if ".." in Path(rel).parts:
        return True
    return False


def _safe_page_path(root: Path, rel: str) -> Path | None:
    """Return resolved page path if it stays under wiki_root and is a file."""
    rel = _normalize_rel(rel)
    if _is_blocked_rel(rel):
        return None
    root_resolved = root.resolve()
    candidate = (root / f"{rel}.md").resolve()
    try:
        candidate.relative_to(root_resolved)
    except ValueError:
        return None
    if not candidate.is_file():
        return None
    return candidate


def _expand_one_hop(root: Path, text: str) -> list[str]:
    neighbors: list[str] = []
    for match in _WIKILINK_RE.finditer(text):
        target = _normalize_rel(match.group(1))
        if _safe_page_path(root, target) is None:
            continue
        if target not in neighbors:
            neighbors.append(target)
    return neighbors


def _parse_index_entries(index_text: str) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    for line in index_text.splitlines():
        match = _INDEX_ENTRY_RE.match(line.strip())
        if not match:
            continue
        path = _normalize_rel(match.group(1))
        if _is_blocked_rel(path):
            continue
        title = (match.group(2) or path.split("/")[-1]).strip()
        blurb = (match.group(3) or "").strip()
        entries.append({"path": path, "title": title, "blurb": blurb})
    return entries


def _page_rel_id(root: Path, file_path: Path) -> str:
    return file_path.relative_to(root).as_posix().removesuffix(".md")


def _read_file_text(file_path: Path) -> str | None:
    try:
        return file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _score_candidates(
    root: Path,
    keywords: list[str],
    candidate_rels: list[str],
) -> list[Hit]:
    scored: list[tuple[float, Hit]] = []
    for rel in candidate_rels:
        file_path = _safe_page_path(root, rel)
        if file_path is None:
            continue
        text = _read_file_text(file_path)
        if text is None:
            continue
        rel_id = _normalize_rel(rel)
        title = _title_from_markdown(text) or rel_id.split("/")[-1]
        title_hits = _keyword_count(keywords, f"{rel_id} {title}")
        body_hits = _keyword_count(keywords, text)
        raw = 2 * title_hits + body_hits
        if raw <= 0:
            continue
        hit = Hit(
            score=float(raw),
            snippet=_excerpt(text),
            hit_type="wiki",
            ref_id=rel_id,
            title=title,
            path=f"{rel_id}.md",
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


def _hits_from_paths(root: Path, paths: list[str], limit: int) -> list[Hit]:
    hits: list[Hit] = []
    for index, raw_rel in enumerate(paths):
        if len(hits) >= limit:
            break
        rel = _normalize_rel(raw_rel)
        file_path = _safe_page_path(root, rel)
        if file_path is None:
            continue
        text = _read_file_text(file_path)
        if text is None:
            continue
        title = _title_from_markdown(text) or rel.split("/")[-1]
        score = 1.0 - index * 0.01
        hits.append(
            Hit(
                score=score,
                snippet=_excerpt(text),
                hit_type="wiki",
                ref_id=rel,
                title=title,
                path=f"{rel}.md",
            )
        )
    return hits


def _strip_json_payload(raw: str) -> str:
    text = raw.strip()
    fence = _JSON_FENCE_RE.search(text)
    if fence:
        return fence.group(1).strip()
    return text


def _llm_select_paths(llm_client, question: str, index_text: str, limit: int) -> list[str]:
    if llm_client is None or not getattr(llm_client, "is_configured", False):
        return []
    prompt = (
        "你是 Wiki 路由助手。根据用户问题，从 index.md 中选择最相关的页面路径。"
        f"最多返回 {limit} 条。只输出 JSON：{{\"paths\": [\"hub/leaf\", ...]}}。\n\n"
        f"## 用户问题\n{question}\n\n## index.md\n{index_text}\n"
    )
    try:
        raw = llm_client.chat_completions(
            [{"role": "user", "content": prompt}],
            temperature=0.0,
            timeout=60.0,
        )
    except Exception:
        return []
    if not isinstance(raw, str):
        return []
    try:
        payload = json.loads(_strip_json_payload(raw))
    except (json.JSONDecodeError, TypeError, ValueError):
        return []
    paths = payload.get("paths") if isinstance(payload, dict) else None
    if not isinstance(paths, list):
        return []
    out: list[str] = []
    for item in paths:
        if isinstance(item, str) and item.strip():
            out.append(item.strip())
        if len(out) >= limit:
            break
    return out


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
            rel = path.relative_to(root).as_posix().removesuffix(".md")
            if _is_blocked_rel(rel):
                continue
            pages.append(path)
        return pages

    def _read_text(self, path: Path) -> str | None:
        return _read_file_text(path)

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
        if not index_path.is_file():
            return []
        index_text = self._read_text(index_path)
        if index_text is None:
            return []
        keywords = extract_keywords(query)
        entries = _parse_index_entries(index_text)
        seeds: list[str] = []
        for entry in entries:
            path = entry["path"]
            if _safe_page_path(root, path) is None:
                continue
            hay = f"{path} {entry['title']} {entry['blurb']}"
            if _keyword_count(keywords, hay) > 0:
                seeds.append(path)
        if seeds:
            candidates: list[str] = []
            for seed in seeds:
                if seed not in candidates:
                    candidates.append(seed)
                seed_file = _safe_page_path(root, seed)
                if seed_file is None:
                    continue
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
        paths = _llm_select_paths(self._llm_client, query, index_text, limit)
        return _hits_from_paths(root, paths, limit)
