from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine

from akos.domain.ports.evidence import EvidenceBundle
from knowledge.models import TextSpan


class PgEvidence:
    """PostgreSQL evidence repository scoped to a single knowledge base."""

    def __init__(self, engine: Engine, knowledge_base_id: str) -> None:
        self._engine = engine
        self._knowledge_base_id = knowledge_base_id

    def bind(self, claim_id: str, source_id: str, span: TextSpan, weight: float) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO claim_evidence (
                        knowledge_base_id, claim_id, source_id,
                        start_pos, end_pos, quote, weight
                    ) VALUES (
                        :knowledge_base_id, :claim_id, :source_id,
                        :start_pos, :end_pos, :quote, :weight
                    )
                    """),
                {
                    "knowledge_base_id": self._knowledge_base_id,
                    "claim_id": claim_id,
                    "source_id": source_id,
                    "start_pos": span.start,
                    "end_pos": span.end,
                    "quote": span.quote,
                    "weight": weight,
                },
            )

    def explain(self, claim_ids: list[str]) -> EvidenceBundle:
        if not claim_ids:
            return EvidenceBundle(conclusion="", items=[], confidence=0.0)

        with self._engine.connect() as conn:
            rows = conn.execute(
                text("""
                    SELECT claim_id, source_id, start_pos, end_pos, quote, weight
                    FROM claim_evidence
                    WHERE knowledge_base_id = :knowledge_base_id
                      AND claim_id = ANY(:claim_ids)
                    ORDER BY id
                    """),
                {
                    "knowledge_base_id": self._knowledge_base_id,
                    "claim_ids": claim_ids,
                },
            ).fetchall()

        items: list[dict] = []
        weights: list[float] = []
        for row in rows:
            items.append(
                {
                    "source_id": row.source_id,
                    "start": row.start_pos,
                    "end": row.end_pos,
                    "quote": row.quote,
                    "weight": row.weight,
                }
            )
            weights.append(row.weight)

        confidence = sum(weights) / len(weights) if weights else 0.0
        conclusion = "; ".join(claim_ids)
        return EvidenceBundle(conclusion=conclusion, items=items, confidence=confidence)
