from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from knowledge.models import Claim, Source


def _row_to_source(row: Any) -> Source:
    return Source(
        id=row.id,
        title=row.title,
        type=row.type,
        uri=row.uri,
        version=row.version,
        created_at=row.created_at,
        status=row.status,
    )


def _row_to_claim(row: Any) -> Claim:
    source_ids = row.source_ids
    if isinstance(source_ids, str):
        source_ids = json.loads(source_ids)
    return Claim(
        id=row.id,
        family_id=row.family_id,
        version=row.version,
        subject=row.subject,
        predicate=row.predicate,
        object=row.object,
        subject_type=row.subject_type,
        object_type=row.object_type,
        confidence=row.confidence,
        status=row.status,
        valid_from=row.valid_from,
        valid_to=row.valid_to,
        source_ids=list(source_ids),
    )


class PgKnowledge:
    """PostgreSQL knowledge repository scoped to a single knowledge base."""

    def __init__(self, engine: Engine, knowledge_base_id: str) -> None:
        self._engine = engine
        self._knowledge_base_id = knowledge_base_id

    def save_source(self, source: Source) -> Source:
        with self._engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO sources (
                        id, knowledge_base_id, title, type, uri, version, created_at, status
                    ) VALUES (
                        :id, :knowledge_base_id, :title, :type, :uri, :version, :created_at, :status
                    )
                    ON CONFLICT (id) DO UPDATE SET
                        title = EXCLUDED.title,
                        type = EXCLUDED.type,
                        uri = EXCLUDED.uri,
                        version = EXCLUDED.version,
                        created_at = EXCLUDED.created_at,
                        status = EXCLUDED.status
                    WHERE sources.knowledge_base_id = EXCLUDED.knowledge_base_id
                    """),
                {
                    "id": source.id,
                    "knowledge_base_id": self._knowledge_base_id,
                    "title": source.title,
                    "type": source.type,
                    "uri": source.uri,
                    "version": source.version,
                    "created_at": source.created_at,
                    "status": source.status,
                },
            )
        return source

    def get_source(self, source_id: str) -> Source | None:
        with self._engine.connect() as conn:
            row = conn.execute(
                text("""
                    SELECT id, title, type, uri, version, created_at, status
                    FROM sources
                    WHERE id = :id AND knowledge_base_id = :knowledge_base_id
                    """),
                {"id": source_id, "knowledge_base_id": self._knowledge_base_id},
            ).one_or_none()
        if row is None:
            return None
        return _row_to_source(row)

    def list_sources(self) -> list[Source]:
        with self._engine.connect() as conn:
            rows = conn.execute(
                text("""
                    SELECT id, title, type, uri, version, created_at, status
                    FROM sources
                    WHERE knowledge_base_id = :knowledge_base_id
                    ORDER BY created_at
                    """),
                {"knowledge_base_id": self._knowledge_base_id},
            ).fetchall()
        return [_row_to_source(row) for row in rows]

    def save_source_text(self, source_id: str, text_content: str) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO source_texts (source_id, knowledge_base_id, text)
                    VALUES (:source_id, :knowledge_base_id, :text)
                    ON CONFLICT (source_id) DO UPDATE SET text = EXCLUDED.text
                    WHERE source_texts.knowledge_base_id = EXCLUDED.knowledge_base_id
                    """),
                {
                    "source_id": source_id,
                    "knowledge_base_id": self._knowledge_base_id,
                    "text": text_content,
                },
            )

    def get_source_text(self, source_id: str) -> str | None:
        with self._engine.connect() as conn:
            row = conn.execute(
                text("""
                    SELECT text
                    FROM source_texts
                    WHERE source_id = :source_id AND knowledge_base_id = :knowledge_base_id
                    """),
                {"source_id": source_id, "knowledge_base_id": self._knowledge_base_id},
            ).one_or_none()
        if row is None:
            return None
        return row.text

    def append_claim(self, claim: Claim) -> Claim:
        with self._engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO claims (
                        id, knowledge_base_id, family_id, version, subject, predicate, object,
                        subject_type, object_type, confidence, status,
                        valid_from, valid_to, source_ids
                    ) VALUES (
                        :id, :knowledge_base_id, :family_id, :version, :subject, :predicate, :object,
                        :subject_type, :object_type, :confidence, :status,
                        :valid_from, :valid_to, CAST(:source_ids AS jsonb)
                    )
                    ON CONFLICT (id) DO NOTHING
                    """),
                {
                    "id": claim.id,
                    "knowledge_base_id": self._knowledge_base_id,
                    "family_id": claim.family_id,
                    "version": claim.version,
                    "subject": claim.subject,
                    "predicate": claim.predicate,
                    "object": claim.object,
                    "subject_type": claim.subject_type,
                    "object_type": claim.object_type,
                    "confidence": claim.confidence,
                    "status": claim.status,
                    "valid_from": claim.valid_from,
                    "valid_to": claim.valid_to,
                    "source_ids": json.dumps(claim.source_ids),
                },
            )
        return claim

    def mark_superseded(self, claim_id: str, valid_to: datetime | None = None) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                text("""
                    UPDATE claims
                    SET status = 'superseded', valid_to = COALESCE(:valid_to, NOW())
                    WHERE id = :claim_id AND knowledge_base_id = :knowledge_base_id
                    """),
                {
                    "claim_id": claim_id,
                    "valid_to": valid_to,
                    "knowledge_base_id": self._knowledge_base_id,
                },
            )

    def get_claim(self, claim_id: str) -> Claim | None:
        with self._engine.connect() as conn:
            row = conn.execute(
                text("""
                    SELECT id, family_id, version, subject, predicate, object,
                           subject_type, object_type, confidence, status,
                           valid_from, valid_to, source_ids
                    FROM claims
                    WHERE id = :id AND knowledge_base_id = :knowledge_base_id
                    """),
                {"id": claim_id, "knowledge_base_id": self._knowledge_base_id},
            ).one_or_none()
        if row is None:
            return None
        return _row_to_claim(row)

    def get_active_claims(self, subject: str, predicate: str | None = None) -> list[Claim]:
        sql = """
            SELECT id, family_id, version, subject, predicate, object,
                   subject_type, object_type, confidence, status,
                   valid_from, valid_to, source_ids
            FROM claims
            WHERE knowledge_base_id = :knowledge_base_id
              AND status = 'active'
              AND subject = :subject
        """
        params: dict[str, Any] = {
            "subject": subject,
            "knowledge_base_id": self._knowledge_base_id,
        }
        if predicate is not None:
            sql += " AND predicate = :predicate"
            params["predicate"] = predicate
        sql += " ORDER BY version"
        with self._engine.connect() as conn:
            rows = conn.execute(text(sql), params).fetchall()
        return [_row_to_claim(row) for row in rows]

    def get_claim_history(self, claim_family_id: str) -> list[Claim]:
        with self._engine.connect() as conn:
            rows = conn.execute(
                text("""
                    SELECT id, family_id, version, subject, predicate, object,
                           subject_type, object_type, confidence, status,
                           valid_from, valid_to, source_ids
                    FROM claims
                    WHERE family_id = :family_id AND knowledge_base_id = :knowledge_base_id
                    ORDER BY version
                    """),
                {"family_id": claim_family_id, "knowledge_base_id": self._knowledge_base_id},
            ).fetchall()
        return [_row_to_claim(row) for row in rows]

    def get_claims_for_source(self, source_id: str) -> list[Claim]:
        with self._engine.connect() as conn:
            rows = conn.execute(
                text("""
                    SELECT id, family_id, version, subject, predicate, object,
                           subject_type, object_type, confidence, status,
                           valid_from, valid_to, source_ids
                    FROM claims
                    WHERE knowledge_base_id = :knowledge_base_id
                      AND source_ids @> CAST(:source_ids AS jsonb)
                    ORDER BY version
                    """),
                {
                    "knowledge_base_id": self._knowledge_base_id,
                    "source_ids": json.dumps([source_id]),
                },
            ).fetchall()
        return [_row_to_claim(row) for row in rows]

    def get_claims_by_status(self, status: str) -> list[Claim]:
        with self._engine.connect() as conn:
            rows = conn.execute(
                text("""
                    SELECT id, family_id, version, subject, predicate, object,
                           subject_type, object_type, confidence, status,
                           valid_from, valid_to, source_ids
                    FROM claims
                    WHERE knowledge_base_id = :knowledge_base_id AND status = :status
                    ORDER BY version
                    """),
                {"knowledge_base_id": self._knowledge_base_id, "status": status},
            ).fetchall()
        return [_row_to_claim(row) for row in rows]

    def as_of(self, query_time: datetime, family_id: str) -> Claim | None:
        with self._engine.connect() as conn:
            row = conn.execute(
                text("""
                    SELECT id, family_id, version, subject, predicate, object,
                           subject_type, object_type, confidence, status,
                           valid_from, valid_to, source_ids
                    FROM claims
                    WHERE knowledge_base_id = :knowledge_base_id
                      AND family_id = :family_id
                      AND valid_from <= :query_time
                      AND (valid_to IS NULL OR valid_to > :query_time)
                    ORDER BY version DESC
                    LIMIT 1
                    """),
                {
                    "knowledge_base_id": self._knowledge_base_id,
                    "family_id": family_id,
                    "query_time": query_time,
                },
            ).one_or_none()
        if row is None:
            return None
        return _row_to_claim(row)

    def add_quarantine(self, reason: str, raw: dict) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO quarantine (knowledge_base_id, reason, raw)
                    VALUES (:knowledge_base_id, :reason, CAST(:raw AS jsonb))
                    """),
                {
                    "knowledge_base_id": self._knowledge_base_id,
                    "reason": reason,
                    "raw": json.dumps(raw),
                },
            )

    def list_quarantine(self) -> list[dict]:
        with self._engine.connect() as conn:
            rows = conn.execute(
                text("""
                    SELECT reason, raw
                    FROM quarantine
                    WHERE knowledge_base_id = :knowledge_base_id
                    ORDER BY id
                    """),
                {"knowledge_base_id": self._knowledge_base_id},
            ).fetchall()
        result: list[dict] = []
        for row in rows:
            raw = row.raw
            if isinstance(raw, str):
                raw = json.loads(raw)
            result.append({"reason": row.reason, "raw": raw})
        return result
