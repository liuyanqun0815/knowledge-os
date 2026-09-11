from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from knowledge.errors import DomainError
from knowledge.models import Claim, Event, Source, SourceChunk, TopicCluster


def _family_id(subject: str, predicate: str, object_type: str) -> str:
    raw = f"{subject}|{predicate}|{object_type}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


class InMemoryKnowledge:
    def __init__(self) -> None:
        self._sources: dict[str, Source] = {}
        self._source_texts: dict[str, str] = {}
        self._claims: dict[str, Claim] = {}
        self._families: dict[str, list[str]] = {}
        self._quarantine: list[dict] = []
        self._quarantine_seq = 0
        self._events: list[Event] = []
        self._chunks: dict[str, SourceChunk] = {}
        self._chunks_by_source: dict[str, list[str]] = {}
        self._topic_clusters: dict[str, TopicCluster] = {}

    def save_source(self, source: Source) -> Source:
        self._sources[source.id] = source
        return source

    def get_source(self, source_id: str) -> Source | None:
        return self._sources.get(source_id)

    def list_sources(self) -> list[Source]:
        return list(self._sources.values())

    def delete_source(self, source_id: str) -> None:
        self._sources.pop(source_id, None)
        self._source_texts.pop(source_id, None)
        self.mark_chunks_stale(source_id)
        for claim in self._claims.values():
            if source_id not in claim.source_ids:
                continue
            if len(claim.source_ids) == 1:
                self.mark_superseded(claim.id)
            else:
                claim.source_ids = [item for item in claim.source_ids if item != source_id]

    def update_source_status(self, source_id: str, status: str) -> None:
        source = self._sources.get(source_id)
        if source is None:
            raise DomainError(f"source_not_found: {source_id}")
        source.status = status

    def save_source_text(self, source_id: str, text: str) -> None:
        self._source_texts[source_id] = text

    def get_source_text(self, source_id: str) -> str | None:
        return self._source_texts.get(source_id)

    def append_claim(self, claim: Claim) -> Claim:
        is_new = claim.id not in self._claims
        self._claims[claim.id] = claim
        if is_new:
            self._families.setdefault(claim.family_id, []).append(claim.id)
        return claim

    def get_claim(self, claim_id: str) -> Claim | None:
        return self._claims.get(claim_id)

    def get_active_claims(self, subject: str, predicate: str | None = None) -> list[Claim]:
        result: list[Claim] = []
        for claim in self._claims.values():
            if claim.status != "active":
                continue
            if claim.subject != subject:
                continue
            if predicate is not None and claim.predicate != predicate:
                continue
            result.append(claim)
        return result

    def get_claim_history(self, claim_family_id: str) -> list[Claim]:
        claim_ids = self._families.get(claim_family_id, [])
        return [self._claims[cid] for cid in claim_ids if cid in self._claims]

    def mark_superseded(self, claim_id: str, valid_to: datetime | None = None) -> None:
        claim = self._claims.get(claim_id)
        if claim is None:
            return
        claim.status = "superseded"
        claim.valid_to = valid_to or datetime.now(timezone.utc)

    def get_claims_for_source(self, source_id: str) -> list[Claim]:
        return [claim for claim in self._claims.values() if source_id in claim.source_ids]

    def get_claims_by_status(self, status: str) -> list[Claim]:
        return [claim for claim in self._claims.values() if claim.status == status]

    def as_of(self, query_time: datetime, family_id: str) -> Claim | None:
        claims = self.get_claim_history(family_id)
        candidates: list[Claim] = []
        for claim in claims:
            if claim.valid_from is not None and claim.valid_from > query_time:
                continue
            if claim.valid_to is not None and query_time >= claim.valid_to:
                continue
            candidates.append(claim)
        if not candidates:
            return None
        return max(candidates, key=lambda claim: claim.version)

    def add_quarantine(self, reason: str, raw: dict) -> None:
        self._quarantine_seq += 1
        self._quarantine.append({"id": self._quarantine_seq, "reason": reason, "raw": raw})

    def list_quarantine(self) -> list[dict]:
        return list(self._quarantine)

    def approve_quarantine(self, quarantine_id: int) -> Claim:
        idx = next((i for i, item in enumerate(self._quarantine) if item["id"] == quarantine_id), None)
        if idx is None:
            raise DomainError(f"quarantine_not_found: {quarantine_id}")

        entry = self._quarantine.pop(idx)
        raw = entry["raw"]

        if "claim_id" in raw:
            claim = self._claims.get(raw["claim_id"])
            if claim is None:
                raise DomainError(f"claim_not_found: {raw['claim_id']}")
            claim.status = "active"
            return claim

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
        return self.append_claim(claim)

    def append_event(self, event: Event) -> Event:
        self._events.append(event)
        return event

    def list_events(self, source_id: str | None = None) -> list[Event]:
        if source_id is None:
            return list(self._events)
        return [event for event in self._events if event.source_id == source_id]

    def save_chunks(self, source_id: str, chunks: list[SourceChunk]) -> None:
        self.mark_chunks_stale(source_id)
        chunk_ids: list[str] = []
        for chunk in chunks:
            self._chunks[chunk.id] = chunk
            chunk_ids.append(chunk.id)
        self._chunks_by_source[source_id] = chunk_ids

    def list_chunks(self, source_id: str, *, status: str = "active") -> list[SourceChunk]:
        chunk_ids = self._chunks_by_source.get(source_id, [])
        return [
            self._chunks[chunk_id]
            for chunk_id in chunk_ids
            if chunk_id in self._chunks and self._chunks[chunk_id].status == status
        ]

    def get_chunk(self, chunk_id: str) -> SourceChunk | None:
        return self._chunks.get(chunk_id)

    def mark_chunks_stale(self, source_id: str) -> None:
        for chunk_id in self._chunks_by_source.get(source_id, []):
            chunk = self._chunks.get(chunk_id)
            if chunk is not None:
                chunk.status = "stale"
        self._chunks_by_source.pop(source_id, None)

    def update_chunk(self, chunk: SourceChunk) -> SourceChunk:
        if chunk.id not in self._chunks:
            raise DomainError(f"chunk_not_found: {chunk.id}")
        self._chunks[chunk.id] = chunk
        return chunk

    def save_topic_clusters(self, clusters: list[TopicCluster]) -> None:
        for cluster in clusters:
            self._topic_clusters[cluster.id] = cluster

    def list_topic_clusters(self, *, status: str = "active") -> list[TopicCluster]:
        return [cluster for cluster in self._topic_clusters.values() if cluster.status == status]

    def get_topic_cluster(self, cluster_id: str) -> TopicCluster | None:
        return self._topic_clusters.get(cluster_id)

    def mark_topic_clusters_stale(self) -> None:
        for cluster in self._topic_clusters.values():
            if cluster.status == "active":
                cluster.status = "stale"
