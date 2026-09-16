from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from retrieval.ports import Hit


def vector_literal(values: list[float]) -> str:
    return "[" + ",".join(f"{value:.8f}" for value in values) + "]"


class PgEmbeddingStore:
    """Persist and search embeddings via pgvector (production path)."""

    def __init__(self, engine: Engine, knowledge_base_id: str, *, dims: int) -> None:
        self._engine = engine
        self._knowledge_base_id = knowledge_base_id
        self._dims = dims

    def upsert(self, ref_type: str, ref_id: str, embedding: list[float]) -> None:
        if len(embedding) != self._dims:
            raise ValueError(f"embedding dimension mismatch: expected {self._dims}, got {len(embedding)}")
        with self._engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO embeddings (knowledge_base_id, ref_type, ref_id, embedding)
                    VALUES (:knowledge_base_id, :ref_type, :ref_id, CAST(:embedding AS vector))
                    ON CONFLICT (knowledge_base_id, ref_type, ref_id) DO UPDATE SET
                        embedding = EXCLUDED.embedding
                    """),
                {
                    "knowledge_base_id": self._knowledge_base_id,
                    "ref_type": ref_type,
                    "ref_id": ref_id,
                    "embedding": vector_literal(embedding),
                },
            )

    def upsert_batch(self, ref_type: str, items: list[tuple[str, list[float]]]) -> None:
        for ref_id, embedding in items:
            self.upsert(ref_type, ref_id, embedding)

    def delete(self, ref_type: str, ref_id: str) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                text("""
                    DELETE FROM embeddings
                    WHERE knowledge_base_id = :knowledge_base_id
                      AND ref_type = :ref_type
                      AND ref_id = :ref_id
                    """),
                {
                    "knowledge_base_id": self._knowledge_base_id,
                    "ref_type": ref_type,
                    "ref_id": ref_id,
                },
            )

    def delete_refs(self, ref_type: str, ref_ids: list[str]) -> None:
        if not ref_ids:
            return
        with self._engine.begin() as conn:
            conn.execute(
                text("""
                    DELETE FROM embeddings
                    WHERE knowledge_base_id = :knowledge_base_id
                      AND ref_type = :ref_type
                      AND ref_id = ANY(CAST(:ref_ids AS text[]))
                    """),
                {
                    "knowledge_base_id": self._knowledge_base_id,
                    "ref_type": ref_type,
                    "ref_ids": ref_ids,
                },
            )

    def search_claims(
        self,
        query_embedding: list[float],
        *,
        top_k: int = 8,
        as_of: datetime | None = None,
    ) -> list[Hit]:
        params: dict[str, Any] = {
            "knowledge_base_id": self._knowledge_base_id,
            "query_embedding": vector_literal(query_embedding),
            "top_k": top_k,
        }
        temporal_sql = ""
        if as_of is not None:
            query_time = as_of if as_of.tzinfo is not None else as_of.replace(tzinfo=timezone.utc)
            params["as_of"] = query_time
            temporal_sql = """
              AND (c.valid_from IS NULL OR c.valid_from <= :as_of)
              AND (c.valid_to IS NULL OR :as_of < c.valid_to)
            """
        with self._engine.connect() as conn:
            rows = conn.execute(
                text(
                    f"""
                    SELECT
                        e.ref_id AS claim_id,
                        1 - (e.embedding <=> CAST(:query_embedding AS vector)) AS score,
                        (c.subject || ' ' || c.predicate || ' ' || c.object) AS snippet
                    FROM embeddings e
                    JOIN claims c
                      ON c.id = e.ref_id
                     AND c.knowledge_base_id = e.knowledge_base_id
                    WHERE e.knowledge_base_id = :knowledge_base_id
                      AND e.ref_type = 'claim'
                      AND c.status = 'active'
                      {temporal_sql}
                    ORDER BY e.embedding <=> CAST(:query_embedding AS vector)
                    LIMIT :top_k
                    """
                ),
                params,
            ).fetchall()
        return [
            Hit(claim_id=row.claim_id, score=float(row.score), snippet=row.snippet, hit_type="claim")
            for row in rows
            if row.claim_id
        ]

    def search_chunks(self, query_embedding: list[float], *, top_k: int = 8) -> list[Hit]:
        with self._engine.connect() as conn:
            rows = conn.execute(
                text("""
                    SELECT
                        e.ref_id AS chunk_id,
                        sc.source_id,
                        1 - (e.embedding <=> CAST(:query_embedding AS vector)) AS score,
                        COALESCE(sc.summary, LEFT(sc.text, 120)) AS snippet
                    FROM embeddings e
                    JOIN source_chunks sc
                      ON sc.id = e.ref_id
                     AND sc.knowledge_base_id = e.knowledge_base_id
                    WHERE e.knowledge_base_id = :knowledge_base_id
                      AND e.ref_type = 'chunk'
                      AND sc.status = 'active'
                    ORDER BY e.embedding <=> CAST(:query_embedding AS vector)
                    LIMIT :top_k
                    """),
                {
                    "knowledge_base_id": self._knowledge_base_id,
                    "query_embedding": vector_literal(query_embedding),
                    "top_k": top_k,
                },
            ).fetchall()
        return [
            Hit(
                score=float(row.score),
                snippet=row.snippet,
                hit_type="chunk",
                chunk_id=row.chunk_id,
                source_id=row.source_id,
            )
            for row in rows
            if row.chunk_id
        ]
