from __future__ import annotations

import hashlib
import math
import re
from datetime import datetime, timezone

from graph.ports import GraphPort
from knowledge.models import Claim
from knowledge.ports import KnowledgePort
from retrieval.ports import Hit, RetrievalMode

_TOP_K = 5
_TOKEN_PATTERN = re.compile(r"[\w\u4e00-\u9fff]+")


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


class HybridRetrieval:
    def __init__(self, knowledge: KnowledgePort, graph: GraphPort) -> None:
        self._knowledge = knowledge
        self._graph = graph
        self._indexed_claims: dict[str, Claim] = {}
        self._claim_vectors: dict[str, list[float]] = {}

    def index_claim(self, claim: Claim) -> None:
        self._indexed_claims[claim.id] = claim
        text = f"{claim.subject} {claim.predicate} {claim.object}"
        self._claim_vectors[claim.id] = _char_hash_vector(text)

    def search(self, query: str, mode: RetrievalMode, filters: dict) -> list[Hit]:
        top_k = int(filters.get("top_k", _TOP_K))
        as_of = filters.get("as_of")
        if mode == RetrievalMode.CLAIM:
            hits = self._search_claim(query, as_of)
        elif mode == RetrievalMode.BM25:
            hits = self._search_bm25(query, as_of)
        elif mode == RetrievalMode.GRAPH:
            hits = self._search_graph(query, as_of)
        elif mode == RetrievalMode.VECTOR:
            hits = self._search_vector(query, as_of)
        else:
            hits = self._merge_hits(
                [
                    self._search_claim(query, as_of),
                    self._search_bm25(query, as_of),
                    self._search_graph(query, as_of),
                    self._search_vector(query, as_of),
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
            text = f"{claim.subject} {claim.predicate} {claim.object}"
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
        for entity_id, entity in self._graph.entities.items():
            name = entity.get("name", "")
            if not name or name not in query:
                continue
            for edge in self._graph.neighbors(entity_id, depth=1):
                claim_id = self._claim_for_subject_entity(edge.src, edge.predicate, edge.dst, as_of)
                snippet = f"{name} {edge.predicate}"
                hits.append(
                    Hit(
                        claim_id=claim_id,
                        score=1.0,
                        snippet=snippet,
                        entity_id=entity_id,
                    )
                )
        return hits

    def _search_vector(self, query: str, as_of: datetime | None = None) -> list[Hit]:
        query_vec = _char_hash_vector(query)
        hits: list[Hit] = []
        for claim_id, claim_vec in self._claim_vectors.items():
            claim = self._indexed_claims[claim_id]
            if not _claim_valid_at(claim, as_of):
                continue
            score = _cosine(query_vec, claim_vec)
            if score <= 0:
                continue
            snippet = f"{claim.subject} {claim.predicate} {claim.object}"
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
        for claim in self._indexed_claims.values():
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

    def _claim_for_subject_entity(
        self,
        src: str,
        predicate: str,
        dst: str,
        as_of: datetime | None = None,
    ) -> str | None:
        src_name = self._graph.entities.get(src, {}).get("name")
        dst_name = self._graph.entities.get(dst, {}).get("name")
        for claim in self._indexed_claims.values():
            if claim.predicate != predicate:
                continue
            if claim.subject == src_name and claim.object == dst_name:
                if _claim_valid_at(claim, as_of):
                    return claim.id
        return None
