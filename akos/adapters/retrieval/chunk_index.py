from __future__ import annotations

import hashlib
import math
import re
from typing import TYPE_CHECKING

from akos.domain.models.knowledge import SourceChunk
from akos.domain.ports.knowledge import KnowledgePort
from akos.domain.ports.retrieval import Hit

if TYPE_CHECKING:
    from akos.adapters.persistence.pg_embeddings import PgEmbeddingStore
    from akos.adapters.retrieval.embedder import EmbedderPort

_TOP_K = 8
_TOKEN_PATTERN = re.compile(r"[\w\u4e00-\u9fff]+")
_LEGACY_HASH_DIMS = 64


def _tokenize(text: str) -> list[str]:
    tokens = _TOKEN_PATTERN.findall(text.lower())
    cjk_chars = [char for char in text if "\u4e00" <= char <= "\u9fff"]
    return tokens + cjk_chars


def _char_hash_vector(text: str, dims: int = _LEGACY_HASH_DIMS) -> list[float]:
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


def _filter_hits_by_min_score(hits: list[Hit], min_score: float, *, top_k: int) -> list[Hit]:
    if min_score <= 0:
        return hits[:top_k]
    filtered = [hit for hit in hits if hit.score >= min_score]
    return filtered[:top_k]


class ChunkRetrieval:
    def __init__(
        self,
        knowledge: KnowledgePort,
        *,
        embedder: EmbedderPort | None = None,
        embedding_store: PgEmbeddingStore | None = None,
    ) -> None:
        self._knowledge = knowledge
        self._embedder = embedder
        self._embedding_store = embedding_store
        self._indexed_chunks: dict[str, SourceChunk] = {}
        self._chunk_vectors: dict[str, list[float]] = {}
        if embedding_store is not None and embedder is None:
            raise ValueError("embedding_store requires embedder")

    @property
    def uses_pg_embeddings(self) -> bool:
        return self._embedding_store is not None

    def index_chunks(self, chunks: list[SourceChunk]) -> None:
        active_chunks = [chunk for chunk in chunks if chunk.status == "active"]
        if self._embedding_store is not None and self._embedder is not None:
            if not active_chunks:
                return
            texts = [_index_text(chunk) for chunk in active_chunks]
            vectors = self._embedder.embed(texts)
            self._embedding_store.upsert_batch("chunk", [(chunk.id, vector) for chunk, vector in zip(active_chunks, vectors)])
            return

        for chunk in active_chunks:
            self._indexed_chunks[chunk.id] = chunk
            self._chunk_vectors[chunk.id] = _char_hash_vector(_index_text(chunk))

    def remove_source(self, source_id: str) -> None:
        if self._embedding_store is not None:
            chunk_ids = [
                chunk.id
                for chunk in self._knowledge.list_chunks(source_id, status="active")
                + self._knowledge.list_chunks(source_id, status="stale")
            ]
            self._embedding_store.delete_refs("chunk", chunk_ids)
            return

        stale_ids = [chunk_id for chunk_id, chunk in self._indexed_chunks.items() if chunk.source_id == source_id]
        for chunk_id in stale_ids:
            self._indexed_chunks.pop(chunk_id, None)
            self._chunk_vectors.pop(chunk_id, None)

    def warm_index(self) -> None:
        """Refresh local caches; skip full re-embed when pgvector store is configured.

        Chunk vector search reads Postgres directly, so rebuilding every embedding
        on orchestrator bootstrap only burns CPU and stalls the first Ask.
        """
        if self._embedding_store is not None and self._embedder is not None:
            return

        self._indexed_chunks.clear()
        self._chunk_vectors.clear()
        for source in self._knowledge.list_sources():
            chunks = self._knowledge.list_chunks(source.id, status="active")
            self.index_chunks(chunks)

    def search(self, query: str, filters: dict) -> list[Hit]:
        top_k = int(filters.get("top_k", _TOP_K))
        min_score = float(filters.get("min_score", 0))
        fetch_k = top_k if min_score <= 0 else max(top_k * 5, 40)
        query_embedding = filters.get("query_embedding")
        if self._embedding_store is not None and self._embedder is not None:
            query_vec = query_embedding if query_embedding is not None else self._embedder.embed([query])[0]
            hits = self._embedding_store.search_chunks(query_vec, top_k=fetch_k)
            return _filter_hits_by_min_score(hits, min_score, top_k=top_k)

        query_tokens = set(_tokenize(query))
        query_vec = query_embedding if query_embedding is not None else _char_hash_vector(query)
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
            if min_score > 0 and score < min_score:
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
