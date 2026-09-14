from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from pathlib import Path

from retrieval.ports import Hit
from wiki.meta import load_pages_meta

_TOP_K = 8
_TOKEN_PATTERN = re.compile(r"[\w\u4e00-\u9fff]+")
_INDEXABLE_PREFIXES = ("topic-", "entity-")


def _tokenize(text: str) -> list[str]:
    tokens = _TOKEN_PATTERN.findall(text.lower())
    cjk_chars = [char for char in text if "\u4e00" <= char <= "\u9fff"]
    return tokens + cjk_chars


def _char_hash_vector(text: str, dims: int = 64) -> list[float]:
    vec = [0.0] * dims
    for token in _tokenize(text):
        digest = hashlib.md5(token.encode()).hexdigest()
        idx = int(digest, 16) % dims
        vec[idx] += 1.0
    norm = math.sqrt(sum(v * v for v in vec))
    if norm == 0:
        return vec
    return [v / norm for v in vec]


def _cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _excerpt(text: str, limit: int = 160) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1] + "…"


@dataclass
class _IndexedPage:
    page_id: str
    title: str
    path: str
    text: str
    vector: list[float]


class WikiPageRetrieval:
    """BM25/char-hash index over compiled wiki topic (and entity) pages."""

    def __init__(self) -> None:
        self._pages: dict[str, _IndexedPage] = {}

    def index_wiki_root(self, root: str | Path) -> None:
        wiki_root = Path(root)
        self._pages.clear()
        if not wiki_root.is_dir():
            return

        meta = load_pages_meta(wiki_root)
        if meta:
            for page_id, page_meta in meta.items():
                rel = page_meta.path
                if not rel:
                    continue
                file_path = wiki_root / rel
                if not file_path.is_file():
                    continue
                text = file_path.read_text(encoding="utf-8")
                title = page_meta.title or page_id
                index_text = f"{title} {text}".strip()
                self._pages[page_id] = _IndexedPage(
                    page_id=page_id,
                    title=title,
                    path=rel.replace("\\", "/"),
                    text=text,
                    vector=_char_hash_vector(index_text),
                )
            return

        for file_path in sorted(wiki_root.rglob("*.md")):
            if ".meta" in file_path.parts:
                continue
            rel = file_path.relative_to(wiki_root).as_posix()
            if rel in {"index.md", "log.md"}:
                continue
            # Flat legacy: only topic-/entity- at root; nested hierarchy pages always indexable
            if "/" not in rel and not file_path.name.startswith(_INDEXABLE_PREFIXES):
                continue
            page_id = rel.removesuffix(".md")
            text = file_path.read_text(encoding="utf-8")
            title = _title_from_markdown(text) or Path(page_id).name
            index_text = f"{title} {text}".strip()
            self._pages[page_id] = _IndexedPage(
                page_id=page_id,
                title=title,
                path=rel,
                text=text,
                vector=_char_hash_vector(index_text),
            )

    def search(self, query: str, top_k: int = _TOP_K) -> list[Hit]:
        if top_k <= 0 or not self._pages:
            return []
        query_tokens = set(_tokenize(query))
        query_vec = _char_hash_vector(query)
        hits: list[Hit] = []

        for page in self._pages.values():
            index_text = f"{page.title} {page.text}".strip()
            doc_tokens = set(_tokenize(index_text))
            overlap = len(query_tokens & doc_tokens) if query_tokens else 0
            bm25_score = overlap / len(query_tokens) if query_tokens else 0.0
            if query and query in index_text:
                bm25_score = max(bm25_score, 1.0)
            vector_score = _cosine(query_vec, page.vector)
            score = bm25_score * 0.6 + vector_score * 0.4
            if score <= 0:
                continue
            hits.append(
                Hit(
                    score=score,
                    snippet=_excerpt(page.text),
                    hit_type="wiki",
                    ref_id=page.page_id,
                    title=page.title,
                    path=page.path,
                )
            )

        hits.sort(key=lambda item: item.score, reverse=True)
        return hits[:top_k]


def _title_from_markdown(text: str) -> str | None:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip() or None
    return None
