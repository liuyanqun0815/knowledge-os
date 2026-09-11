from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from knowledge.errors import DomainError
from knowledge.models import Claim, Event, Source, SourceChunk, TopicCluster


def _family_id(subject: str, predicate: str, object_type: str) -> str:
    raw = f"{subject}|{predicate}|{object_type}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _row_to_source(row: Any) -> Source:
    replaces = getattr(row, "replaces_source_id", None)
    return Source(
        id=row.id,
        title=row.title,
        type=row.type,
        uri=row.uri,
        version=row.version,
        created_at=row.created_at,
        status=row.status,
        replaces_source_id=replaces,
    )


def _row_to_event(row: Any) -> Event:
    participants = row.participants
    if isinstance(participants, str):
        participants = json.loads(participants)
    return Event(
        id=row.id,
        type=row.type,
        participants=list(participants),
        timestamp=row.timestamp,
        source_id=row.source_id,
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
                        id, knowledge_base_id, title, type, uri, version, created_at, status,
                        replaces_source_id
                    ) VALUES (
                        :id, :knowledge_base_id, :title, :type, :uri, :version, :created_at, :status,
                        :replaces_source_id
                    )
                    ON CONFLICT (id) DO UPDATE SET
                        title = EXCLUDED.title,
                        type = EXCLUDED.type,
                        uri = EXCLUDED.uri,
                        version = EXCLUDED.version,
                        created_at = EXCLUDED.created_at,
                        status = EXCLUDED.status,
                        replaces_source_id = EXCLUDED.replaces_source_id
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
                    "replaces_source_id": source.replaces_source_id,
                },
            )
        return source

    def get_source(self, source_id: str) -> Source | None:
        with self._engine.connect() as conn:
            row = conn.execute(
                text("""
                    SELECT id, title, type, uri, version, created_at, status, replaces_source_id
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
                    SELECT id, title, type, uri, version, created_at, status, replaces_source_id
                    FROM sources
                    WHERE knowledge_base_id = :knowledge_base_id
                    ORDER BY created_at
                    """),
                {"knowledge_base_id": self._knowledge_base_id},
            ).fetchall()
        return [_row_to_source(row) for row in rows]

    def delete_source(self, source_id: str) -> None:
        params = {
            "source_id": source_id,
            "knowledge_base_id": self._knowledge_base_id,
            "source_ids": json.dumps([source_id]),
        }
        with self._engine.begin() as conn:
            conn.execute(
                text("""
                    UPDATE claims
                    SET status = 'superseded', valid_to = COALESCE(valid_to, NOW())
                    WHERE knowledge_base_id = :knowledge_base_id
                      AND source_ids @> CAST(:source_ids AS jsonb)
                      AND jsonb_array_length(source_ids) = 1
                    """),
                params,
            )
            conn.execute(
                text("""
                    UPDATE claims
                    SET source_ids = source_ids - CAST(:source_id AS text)
                    WHERE knowledge_base_id = :knowledge_base_id
                      AND source_ids @> CAST(:source_ids AS jsonb)
                      AND jsonb_array_length(source_ids) > 1
                    """),
                params,
            )
            conn.execute(
                text("""
                    DELETE FROM claim_evidence
                    WHERE source_id = :source_id AND knowledge_base_id = :knowledge_base_id
                    """),
                params,
            )
            conn.execute(
                text("""
                    DELETE FROM events
                    WHERE source_id = :source_id AND knowledge_base_id = :knowledge_base_id
                    """),
                params,
            )
            conn.execute(
                text("""
                    UPDATE sources
                    SET replaces_source_id = NULL
                    WHERE replaces_source_id = :source_id AND knowledge_base_id = :knowledge_base_id
                    """),
                params,
            )
            conn.execute(
                text("""
                    DELETE FROM source_texts
                    WHERE source_id = :source_id AND knowledge_base_id = :knowledge_base_id
                    """),
                params,
            )
            conn.execute(
                text("""
                    DELETE FROM sources
                    WHERE id = :source_id AND knowledge_base_id = :knowledge_base_id
                    """),
                params,
            )

    def update_source_status(self, source_id: str, status: str) -> None:
        with self._engine.begin() as conn:
            result = conn.execute(
                text("""
                    UPDATE sources
                    SET status = :status
                    WHERE id = :source_id AND knowledge_base_id = :knowledge_base_id
                    """),
                {
                    "source_id": source_id,
                    "knowledge_base_id": self._knowledge_base_id,
                    "status": status,
                },
            )
        if result.rowcount == 0:
            raise DomainError(f"source_not_found: {source_id}")

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
                    SELECT id, reason, raw
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
            result.append({"id": row.id, "reason": row.reason, "raw": raw})
        return result

    def approve_quarantine(self, quarantine_id: int) -> Claim:
        with self._engine.begin() as conn:
            row = conn.execute(
                text("""
                    SELECT id, reason, raw
                    FROM quarantine
                    WHERE id = :quarantine_id AND knowledge_base_id = :knowledge_base_id
                    """),
                {"quarantine_id": quarantine_id, "knowledge_base_id": self._knowledge_base_id},
            ).one_or_none()
            if row is None:
                raise DomainError(f"quarantine_not_found: {quarantine_id}")

            raw = row.raw
            if isinstance(raw, str):
                raw = json.loads(raw)

            conn.execute(
                text("""
                    DELETE FROM quarantine
                    WHERE id = :quarantine_id AND knowledge_base_id = :knowledge_base_id
                    """),
                {"quarantine_id": quarantine_id, "knowledge_base_id": self._knowledge_base_id},
            )

            if "claim_id" in raw:
                claim_id = raw["claim_id"]
                updated = conn.execute(
                    text("""
                        UPDATE claims
                        SET status = 'active'
                        WHERE id = :claim_id AND knowledge_base_id = :knowledge_base_id
                        RETURNING id, family_id, version, subject, predicate, object,
                                  subject_type, object_type, confidence, status,
                                  valid_from, valid_to, source_ids
                        """),
                    {"claim_id": claim_id, "knowledge_base_id": self._knowledge_base_id},
                ).one_or_none()
                if updated is None:
                    raise DomainError(f"claim_not_found: {claim_id}")
                return _row_to_claim(updated)

            required = ("subject", "predicate", "object")
            missing = [field for field in required if field not in raw]
            if missing:
                raise DomainError(f"quarantine_raw_incomplete: missing {','.join(missing)}")

            subject_type = raw.get("subject_type", "Concept")
            object_type = raw.get("object_type", "Concept")
            source_ids = [raw["source_id"]] if raw.get("source_id") else []
            claim = Claim(
                id=str(uuid.uuid4()),
                family_id=_family_id(raw["subject"], raw["predicate"], object_type),
                version=1,
                subject=raw["subject"],
                predicate=raw["predicate"],
                object=raw["object"],
                subject_type=subject_type,
                object_type=object_type,
                confidence=float(raw.get("confidence", 0.8)),
                status="active",
                valid_from=datetime.now(timezone.utc),
                valid_to=None,
                source_ids=source_ids,
            )
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

    def append_event(self, event: Event) -> Event:
        with self._engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO events (
                        id, knowledge_base_id, type, participants, timestamp, source_id
                    ) VALUES (
                        :id, :knowledge_base_id, :type, CAST(:participants AS jsonb),
                        :timestamp, :source_id
                    )
                    ON CONFLICT (id) DO NOTHING
                    """),
                {
                    "id": event.id,
                    "knowledge_base_id": self._knowledge_base_id,
                    "type": event.type,
                    "participants": json.dumps(event.participants),
                    "timestamp": event.timestamp,
                    "source_id": event.source_id,
                },
            )
        return event

    def list_events(self, source_id: str | None = None) -> list[Event]:
        sql = """
            SELECT id, type, participants, timestamp, source_id
            FROM events
            WHERE knowledge_base_id = :knowledge_base_id
        """
        params: dict[str, Any] = {"knowledge_base_id": self._knowledge_base_id}
        if source_id is not None:
            sql += " AND source_id = :source_id"
            params["source_id"] = source_id
        sql += " ORDER BY timestamp"
        with self._engine.connect() as conn:
            rows = conn.execute(text(sql), params).fetchall()
        return [_row_to_event(row) for row in rows]

    def save_chunks(self, source_id: str, chunks: list[SourceChunk]) -> None:
        self.mark_chunks_stale(source_id)
        with self._engine.begin() as conn:
            for chunk in chunks:
                conn.execute(
                    text("""
                        INSERT INTO source_chunks (
                            id, knowledge_base_id, source_id, chunk_index, title, summary, text,
                            start_offset, end_offset, section_path, topics, token_count, status,
                            content_hash, created_at
                        ) VALUES (
                            :id, :knowledge_base_id, :source_id, :chunk_index, :title, :summary, :text,
                            :start_offset, :end_offset, CAST(:section_path AS jsonb), CAST(:topics AS jsonb),
                            :token_count, :status, :content_hash, :created_at
                        )
                        """),
                    {
                        "id": chunk.id,
                        "knowledge_base_id": self._knowledge_base_id,
                        "source_id": source_id,
                        "chunk_index": chunk.chunk_index,
                        "title": chunk.title,
                        "summary": chunk.summary,
                        "text": chunk.text,
                        "start_offset": chunk.start,
                        "end_offset": chunk.end,
                        "section_path": json.dumps(chunk.section_path),
                        "topics": json.dumps(chunk.topics),
                        "token_count": chunk.token_count,
                        "status": chunk.status,
                        "content_hash": chunk.content_hash,
                        "created_at": chunk.created_at or datetime.now(timezone.utc),
                    },
                )

    def list_chunks(self, source_id: str, *, status: str = "active") -> list[SourceChunk]:
        with self._engine.connect() as conn:
            rows = conn.execute(
                text("""
                    SELECT id, source_id, chunk_index, title, summary, text, start_offset, end_offset,
                           section_path, topics, token_count, status, content_hash, created_at
                    FROM source_chunks
                    WHERE knowledge_base_id = :knowledge_base_id
                      AND source_id = :source_id
                      AND status = :status
                    ORDER BY chunk_index
                    """),
                {
                    "knowledge_base_id": self._knowledge_base_id,
                    "source_id": source_id,
                    "status": status,
                },
            ).fetchall()
        return [self._row_to_chunk(row) for row in rows]

    def get_chunk(self, chunk_id: str) -> SourceChunk | None:
        with self._engine.connect() as conn:
            row = conn.execute(
                text("""
                    SELECT id, source_id, chunk_index, title, summary, text, start_offset, end_offset,
                           section_path, topics, token_count, status, content_hash, created_at
                    FROM source_chunks
                    WHERE id = :id AND knowledge_base_id = :knowledge_base_id
                    """),
                {"id": chunk_id, "knowledge_base_id": self._knowledge_base_id},
            ).one_or_none()
        return self._row_to_chunk(row) if row is not None else None

    def mark_chunks_stale(self, source_id: str) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                text("""
                    UPDATE source_chunks
                    SET status = 'stale'
                    WHERE knowledge_base_id = :knowledge_base_id AND source_id = :source_id
                    """),
                {"knowledge_base_id": self._knowledge_base_id, "source_id": source_id},
            )

    def update_chunk(self, chunk: SourceChunk) -> SourceChunk:
        with self._engine.begin() as conn:
            conn.execute(
                text("""
                    UPDATE source_chunks
                    SET title = :title,
                        summary = :summary,
                        topics = CAST(:topics AS jsonb),
                        token_count = :token_count,
                        content_hash = :content_hash
                    WHERE id = :id AND knowledge_base_id = :knowledge_base_id
                    """),
                {
                    "id": chunk.id,
                    "knowledge_base_id": self._knowledge_base_id,
                    "title": chunk.title,
                    "summary": chunk.summary,
                    "topics": json.dumps(chunk.topics),
                    "token_count": chunk.token_count,
                    "content_hash": chunk.content_hash,
                },
            )
        return chunk

    def save_topic_clusters(self, clusters: list[TopicCluster]) -> None:
        with self._engine.begin() as conn:
            for cluster in clusters:
                conn.execute(
                    text("""
                        INSERT INTO topic_clusters (
                            id, knowledge_base_id, name, aliases, chunk_ids, claim_ids,
                            source_ids, summary, status, content_hash, updated_at
                        ) VALUES (
                            :id, :knowledge_base_id, :name, CAST(:aliases AS jsonb),
                            CAST(:chunk_ids AS jsonb), CAST(:claim_ids AS jsonb),
                            CAST(:source_ids AS jsonb), :summary, :status, :content_hash, :updated_at
                        )
                        ON CONFLICT (id) DO UPDATE SET
                            name = EXCLUDED.name,
                            aliases = EXCLUDED.aliases,
                            chunk_ids = EXCLUDED.chunk_ids,
                            claim_ids = EXCLUDED.claim_ids,
                            source_ids = EXCLUDED.source_ids,
                            summary = EXCLUDED.summary,
                            status = EXCLUDED.status,
                            content_hash = EXCLUDED.content_hash,
                            updated_at = EXCLUDED.updated_at
                        """),
                    {
                        "id": cluster.id,
                        "knowledge_base_id": self._knowledge_base_id,
                        "name": cluster.name,
                        "aliases": json.dumps(cluster.aliases),
                        "chunk_ids": json.dumps(cluster.chunk_ids),
                        "claim_ids": json.dumps(cluster.claim_ids),
                        "source_ids": json.dumps(cluster.source_ids),
                        "summary": cluster.summary,
                        "status": cluster.status,
                        "content_hash": cluster.content_hash,
                        "updated_at": cluster.updated_at or datetime.now(timezone.utc),
                    },
                )

    def list_topic_clusters(self, *, status: str = "active") -> list[TopicCluster]:
        with self._engine.connect() as conn:
            rows = conn.execute(
                text("""
                    SELECT id, knowledge_base_id, name, aliases, chunk_ids, claim_ids,
                           source_ids, summary, status, content_hash, updated_at
                    FROM topic_clusters
                    WHERE knowledge_base_id = :knowledge_base_id AND status = :status
                    ORDER BY name
                    """),
                {"knowledge_base_id": self._knowledge_base_id, "status": status},
            ).fetchall()
        return [self._row_to_topic_cluster(row) for row in rows]

    def get_topic_cluster(self, cluster_id: str) -> TopicCluster | None:
        with self._engine.connect() as conn:
            row = conn.execute(
                text("""
                    SELECT id, knowledge_base_id, name, aliases, chunk_ids, claim_ids,
                           source_ids, summary, status, content_hash, updated_at
                    FROM topic_clusters
                    WHERE id = :id AND knowledge_base_id = :knowledge_base_id
                    """),
                {"id": cluster_id, "knowledge_base_id": self._knowledge_base_id},
            ).one_or_none()
        return self._row_to_topic_cluster(row) if row is not None else None

    def mark_topic_clusters_stale(self) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                text("""
                    UPDATE topic_clusters
                    SET status = 'stale'
                    WHERE knowledge_base_id = :knowledge_base_id AND status = 'active'
                    """),
                {"knowledge_base_id": self._knowledge_base_id},
            )

    @staticmethod
    def _row_to_topic_cluster(row: Any) -> TopicCluster:
        aliases = row.aliases
        if isinstance(aliases, str):
            aliases = json.loads(aliases)
        chunk_ids = row.chunk_ids
        if isinstance(chunk_ids, str):
            chunk_ids = json.loads(chunk_ids)
        claim_ids = row.claim_ids
        if isinstance(claim_ids, str):
            claim_ids = json.loads(claim_ids)
        source_ids = row.source_ids
        if isinstance(source_ids, str):
            source_ids = json.loads(source_ids)
        return TopicCluster(
            id=row.id,
            knowledge_base_id=row.knowledge_base_id,
            name=row.name,
            aliases=list(aliases or []),
            chunk_ids=list(chunk_ids or []),
            claim_ids=list(claim_ids or []),
            source_ids=list(source_ids or []),
            summary=row.summary,
            status=row.status,
            content_hash=row.content_hash,
            updated_at=row.updated_at,
        )

    @staticmethod
    def _row_to_chunk(row: Any) -> SourceChunk:
        section_path = row.section_path
        if isinstance(section_path, str):
            section_path = json.loads(section_path)
        topics = row.topics
        if isinstance(topics, str):
            topics = json.loads(topics)
        return SourceChunk(
            id=row.id,
            source_id=row.source_id,
            chunk_index=row.chunk_index,
            title=row.title,
            summary=row.summary,
            text=row.text,
            start=row.start_offset,
            end=row.end_offset,
            section_path=list(section_path or []),
            topics=list(topics or []),
            token_count=row.token_count or 0,
            status=row.status,
            content_hash=row.content_hash,
            created_at=row.created_at,
        )
