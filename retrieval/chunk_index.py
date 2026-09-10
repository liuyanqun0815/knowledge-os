from __future__ import annotations

import hashlib
import math
import re

from knowledge.models import SourceChunk
from knowledge.ports import KnowledgePort
from retrieval.ports import Hit

_TOP_K = 8
_TOKEN_PATTERN = re.compile(r"[\w\u4e00-\u9fff]+")


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


def _index_text(chunk: SourceChunk) -> str:
    title = chunk.title or ""
    summary = chunk.summary or ""
    topics = " ".join(chunk.topics)
    return f"{title} {summary} {topics} {chunk.text}".strip()


class ChunkRetrieval:
    def __init__(self, knowledge: KnowledgePort) -> None:
        self._knowledge = knowledge
        self._indexed_chunks: dict[str, SourceChunk] = {}
        self._chunk_vectors: dict[str, list[float]] = {}

    def index_chunks(self, chunks: list[SourceChunk]) -> None:
        for chunk in chunks:
            if chunk.status != "active":
                continue
            self._indexed_chunks[chunk.id] = chunk
            self._chunk_vectors[chunk.id] = _char_hash_vector(_index_text(chunk))

    def remove_source(self, source_id: str) -> None:
        stale_ids = [chunk_id for chunk_id, chunk in self._indexed_chunks.items() if chunk.source_id == source_id]
        for chunk_id in stale_ids:
            self._indexed_chunks.pop(chunk_id, None)
            self._chunk_vectors.pop(chunk_id, None)

    def warm_index(self) -> None:
        self._indexed_chunks.clear()
        self._chunk_vectors.clear()
        for source in self._knowledge.list_sources():
            chunks = self._knowledge.list_chunks(source.id, status="active")
            self.index_chunks(chunks)

    def search(self, query: str, filters: dict) -> list[Hit]:
        top_k = int(filters.get("top_k", _TOP_K))
        query_tokens = set(_tokenize(query))
        query_vec = _char_hash_vector(query)
        hits: list[Hit] = []

        for chunk_id, chunk in self._indexed_chunks.items():
            index_text = _index_text(chunk)
            doc_tokens = set(_tokenize(index_text))
            overlap = len(query_tokens & doc_tokens) if query_tokens else 0
            bm25_score = overlap / len(query_tokens) if query_tokens else 0.0
            if query and query in index_text:
                bm25_score = max(bm25_score, 1.0)
            vector_score = _cosine(query_vec, self._chunk_vectors[chunk_id])
            score = bm25_score * 0.6 + vector_score * 0.4
            if score <= 0:
                continue
            excerpt = chunk.summary or chunk.text[:120]
            hits.append(
                Hit(
                    score=score,
                    snippet=excerpt,
                    hit_type="chunk",
                    chunk_id=chunk_id,
                    source_id=chunk.source_id,
                )
            )

        hits.sort(key=lambda item: item.score, reverse=True)
        return hits[:top_k]
