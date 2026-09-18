from __future__ import annotations

import hashlib
import math
import re
import threading
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from akos.domain.ports.graph import GraphPort
from akos.domain.models.knowledge import Claim
from akos.domain.ports.knowledge import KnowledgePort
from akos.adapters.retrieval.embedder import EmbedderPort, claim_embedding_text
from akos.domain.ports.retrieval import Hit, RetrievalMode

if TYPE_CHECKING:
    from akos.adapters.persistence.pg_embeddings import PgEmbeddingStore

_TOP_K = 8
_GRAPH_MAX_DEPTH = 2
_TOKEN_PATTERN = re.compile(r"[\w\u4e00-\u9fff]+")
_LEGACY_HASH_DIMS = 64


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _claim_valid_at(claim: Claim, as_of: datetime | None) -> bool:
    if as_of is None:
        return claim.status == "active"
    query_time = _ensure_utc(as_of)
    if claim.valid_from is not None and claim.valid_from > query_time:
        return False
    if claim.valid_to is not None and query_time >= claim.valid_to:
        return False
    return True


def _tokenize(text: str) -> list[str]:
    return _TOKEN_PATTERN.findall(text.lower())


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


class HybridRetrieval:
    def __init__(
        self,
        knowledge: KnowledgePort,
        graph: GraphPort,
        *,
        embedder: EmbedderPort | None = None,
        embedding_store: PgEmbeddingStore | None = None,
    ) -> None:
        self._knowledge = knowledge
        self._graph = graph
        self._embedder = embedder
        self._embedding_store = embedding_store
        self._indexed_claims: dict[str, Claim] = {}
        self._claim_vectors: dict[str, list[float]] = {}
        self._lock = threading.RLock()
        if embedding_store is not None and embedder is None:
            raise ValueError("embedding_store requires embedder")

    @property
    def uses_pg_embeddings(self) -> bool:
        return self._embedding_store is not None

    def index_claim(self, claim: Claim) -> None:
        with self._lock:
            self._index_claim_unlocked(claim)

    def remove_claim(self, claim_id: str) -> None:
        with self._lock:
            self._indexed_claims.pop(claim_id, None)
            self._claim_vectors.pop(claim_id, None)
            if self._embedding_store is not None:
                self._embedding_store.delete("claim", claim_id)

    def _index_claim_unlocked(self, claim: Claim) -> None:
        self._indexed_claims[claim.id] = claim
        if self._embedding_store is not None and self._embedder is not None and claim.status == "active":
            text = claim_embedding_text(claim.subject, claim.predicate, claim.object)
            vector = self._embedder.embed([text])[0]
            self._embedding_store.upsert("claim", claim.id, vector)
            return
        text = claim_embedding_text(claim.subject, claim.predicate, claim.object)
        self._claim_vectors[claim.id] = _char_hash_vector(text)

    def warm_index(self) -> None:
        """Refresh in-memory claim cache; reuse existing pgvector rows when available.

        Re-embedding every active claim on each orchestrator build blocks Ask for
        minutes on CPU. With PgEmbeddingStore, vector search already hits Postgres,
        so warm only needs the metadata cache used by BM25/graph/claim modes.
        """
        with self._lock:
            self._indexed_claims.clear()
            self._claim_vectors.clear()
            active_claims = self._knowledge.get_claims_by_status("active")
            if self._embedding_store is not None and self._embedder is not None:
                for claim in active_claims:
                    self._indexed_claims[claim.id] = claim
                return
            for claim in active_claims:
                self._index_claim_unlocked(claim)

    def search(self, query: str, mode: RetrievalMode, filters: dict) -> list[Hit]:
        with self._lock:
            return self._search_unlocked(query, mode, filters)

    def _search_unlocked(self, query: str, mode: RetrievalMode, filters: dict) -> list[Hit]:
        top_k = int(filters.get("top_k", _TOP_K))
        as_of = filters.get("as_of")
        query_embedding = filters.get("query_embedding")
        if mode == RetrievalMode.CLAIM:
            hits = self._search_claim(query, as_of)
        elif mode == RetrievalMode.BM25:
            hits = self._search_bm25(query, as_of)
        elif mode == RetrievalMode.GRAPH:
            hits = self._search_graph(query, as_of)
        elif mode == RetrievalMode.VECTOR:
            hits = self._search_vector(query, as_of, top_k=top_k, query_embedding=query_embedding)
        else:
            hits = self._merge_hits(
                [
                    self._search_claim(query, as_of),
                    self._search_bm25(query, as_of),
                    self._search_graph(query, as_of),
                    self._search_vector(query, as_of, top_k=top_k, query_embedding=query_embedding),
                ]
            )
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[:top_k]

    def _search_claim(self, query: str, as_of: datetime | None = None) -> list[Hit]:
        hits: list[Hit] = []
        query_lower = query.lower()
        for claim in self._indexed_claims.values():
            if not _claim_valid_at(claim, as_of):
                continue
            text = claim_embedding_text(claim.subject, claim.predicate, claim.object)
            score = 0.0
            for part in (claim.subject, claim.predicate, claim.object):
                if part and part.lower() in query_lower:
                    score += 1.0
            if score > 0:
                hits.append(Hit(claim_id=claim.id, score=score, snippet=text))
        return hits

    def _search_bm25(self, query: str, as_of: datetime | None = None) -> list[Hit]:
        query_tokens = set(_tokenize(query))
        if not query_tokens:
            return []

        hits: list[Hit] = []
        for source_id, text in self._iter_source_texts():
            doc_tokens = set(_tokenize(text))
            overlap = len(query_tokens & doc_tokens)
            if overlap == 0:
                continue
            score = overlap / len(query_tokens)
            snippet = self._snippet_for_overlap(text, query_tokens)
            claim_id = self._claim_for_source(source_id, as_of)
            hits.append(Hit(claim_id=claim_id, score=score, snippet=snippet))
        return hits

    def _search_graph(self, query: str, as_of: datetime | None = None) -> list[Hit]:
        hits: list[Hit] = []
        seed_entities: list[tuple[str, str]] = []
        for entity_id, entity in self._graph.list_entities():
            name = entity.get("name", "")
            if not name or name not in query:
                continue
            seed_entities.append((entity_id, name))

        visited_edges: set[tuple[str, str, str]] = set()
        for entity_id, name in seed_entities:
            frontier: list[tuple[str, int]] = [(entity_id, 0)]
            seen_nodes: set[str] = {entity_id}
            while frontier:
                current_id, hop = frontier.pop(0)
                if hop >= _GRAPH_MAX_DEPTH:
                    continue
                for edge in self._graph.neighbors(current_id, depth=1):
                    edge_key = (edge.src, edge.predicate, edge.dst)
                    if edge_key in visited_edges:
                        continue
                    visited_edges.add(edge_key)
                    claim_id = self._claim_for_subject_entity(edge.src, edge.predicate, edge.dst, as_of)
                    src_name = self._entity_name(edge.src) or name
                    dst_name = self._entity_name(edge.dst) or ""
                    snippet = f"{src_name} {edge.predicate} {dst_name}".strip()
                    score = 1.0 / (hop + 1)
                    hits.append(
                        Hit(
                            claim_id=claim_id,
                            score=score,
                            snippet=snippet,
                            entity_id=edge.src,
                        )
                    )
                    if edge.dst not in seen_nodes and hop + 1 < _GRAPH_MAX_DEPTH:
                        seen_nodes.add(edge.dst)
                        frontier.append((edge.dst, hop + 1))
        return hits

    def _search_vector(
        self,
        query: str,
        as_of: datetime | None = None,
        *,
        top_k: int = _TOP_K,
        query_embedding: list[float] | None = None,
    ) -> list[Hit]:
        if self._embedding_store is not None and self._embedder is not None:
            query_vec = query_embedding if query_embedding is not None else self._embedder.embed([query])[0]
            return self._embedding_store.search_claims(query_vec, top_k=top_k, as_of=as_of)

        query_vec = query_embedding if query_embedding is not None else _char_hash_vector(query)
        hits: list[Hit] = []
        for claim_id, claim_vec in self._claim_vectors.items():
            claim = self._indexed_claims.get(claim_id)
            if claim is None or not _claim_valid_at(claim, as_of):
                continue
            score = _cosine(query_vec, claim_vec)
            if score <= 0:
                continue
            snippet = claim_embedding_text(claim.subject, claim.predicate, claim.object)
            hits.append(Hit(claim_id=claim_id, score=score, snippet=snippet))
        return hits

    def _merge_hits(self, hit_groups: list[list[Hit]]) -> list[Hit]:
        merged: dict[str, Hit] = {}
        for group in hit_groups:
            for hit in group:
                key = hit.claim_id or hit.snippet or str(id(hit))
                existing = merged.get(key)
                if existing is None or hit.score > existing.score:
                    merged[key] = hit
                elif hit.score == existing.score and hit.snippet and not existing.snippet:
                    merged[key] = hit
        return list(merged.values())

    def _iter_source_texts(self) -> list[tuple[str, str]]:
        texts: list[tuple[str, str]] = []
        seen: set[str] = set()
        for claim in list(self._indexed_claims.values()):
            for source_id in claim.source_ids:
                if source_id in seen:
                    continue
                text = self._knowledge.get_source_text(source_id)
                if text:
                    texts.append((source_id, text))
                    seen.add(source_id)
        return texts

    def _snippet_for_overlap(self, text: str, query_tokens: set[str]) -> str:
        for token in query_tokens:
            idx = text.find(token)
            if idx >= 0:
                start = max(0, idx - 10)
                end = min(len(text), idx + len(token) + 20)
                return text[start:end]
        return text[:40]

    def _claim_for_source(self, source_id: str, as_of: datetime | None = None) -> str | None:
        for claim in self._indexed_claims.values():
            if source_id not in claim.source_ids:
                continue
            if _claim_valid_at(claim, as_of):
                return claim.id
        return None

    def _entity_name(self, entity_id: str) -> str | None:
        entity = self._graph.get_entity(entity_id)
        if not entity:
            return None
        name = entity.get("name")
        return name if isinstance(name, str) else None

    def _claim_for_subject_entity(
        self,
        src: str,
        predicate: str,
        dst: str,
        as_of: datetime | None = None,
    ) -> str | None:
        src_name = self._entity_name(src)
        dst_name = self._entity_name(dst)
        for claim in self._indexed_claims.values():
            if claim.predicate != predicate:
                continue
            if claim.subject == src_name and claim.object == dst_name:
                if _claim_valid_at(claim, as_of):
                    return claim.id
        return None
