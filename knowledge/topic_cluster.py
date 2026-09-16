from __future__ import annotations

import hashlib
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone

import re

from knowledge.models import Claim, SourceChunk, TopicCluster

DEFAULT_TOPIC_ALIASES: dict[str, str] = {
    "尺码表": "尺码选择",
    "尺码指南": "尺码选择",
}

_ENTITY_SUBJECT = re.compile(
    r"^(女装|男装)?尺码[A-Z0-9XL]+$|^中国码\d+$|^欧码\d+$|^美码[\d.]+$",
    re.IGNORECASE,
)


def _claim_subject_as_topic(subject: str) -> bool:
    """Skip table-row / size-code entities as standalone topics."""
    text = subject.strip()
    if not text or len(text) <= 2:
        return False
    if _ENTITY_SUBJECT.match(text):
        return False
    if re.match(r"^[\d\-~、，,cm\s]+$", text):
        return False
    if len(text) > 48 and ("、" in text or "，" in text):
        return False
    return True


def _merge_aliases(custom: dict[str, str] | None) -> dict[str, str]:
    merged = dict(DEFAULT_TOPIC_ALIASES)
    if custom:
        merged.update(custom)
    return merged


def _strip_punctuation(text: str) -> str:
    return re.sub(r"[\s\W_]+", "", text, flags=re.UNICODE)


def normalize_topic_name(raw: str, aliases: dict[str, str] | None = None) -> str:
    alias_map = _merge_aliases(aliases)
    normalized = _strip_punctuation(raw.strip().lower())
    if not normalized:
        return normalized
    if normalized in alias_map:
        return alias_map[normalized]
    canonical_values = sorted(set(alias_map.values()), key=len, reverse=True)
    for canonical in canonical_values:
        if normalized.startswith(canonical):
            return canonical
    return normalized


def _cluster_content_hash(chunk_ids: list[str], claim_ids: list[str]) -> str:
    payload = ",".join(sorted(chunk_ids)) + "|" + ",".join(sorted(claim_ids))
    return hashlib.sha256(payload.encode()).hexdigest()


def _cluster_id(knowledge_base_id: str, canonical_name: str) -> str:
    raw = f"{knowledge_base_id}|{canonical_name}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


@dataclass
class _TopicBucket:
    canonical_name: str
    raw_counts: Counter[str] = field(default_factory=Counter)
    chunk_ids: set[str] = field(default_factory=set)
    claim_ids: set[str] = field(default_factory=set)
    source_ids: set[str] = field(default_factory=set)

    def record_raw(self, raw: str) -> None:
        if raw:
            self.raw_counts[raw] += 1

    def display_name(self) -> str:
        if not self.raw_counts:
            return self.canonical_name
        return self.raw_counts.most_common(1)[0][0]

    def alias_names(self, display_name: str) -> list[str]:
        aliases = [raw for raw in self.raw_counts if raw != display_name]
        if self.canonical_name != display_name and self.canonical_name not in aliases:
            aliases.append(self.canonical_name)
        return sorted(set(aliases))


def _candidate_topics(chunk: SourceChunk) -> list[str]:
    candidates = list(chunk.topics)
    if chunk.section_path:
        candidates.append(chunk.section_path[-1])
    return candidates


def build_topic_clusters(
    *,
    knowledge_base_id: str,
    chunks: list[SourceChunk],
    claims: list[Claim],
    min_chunks: int = 1,
    aliases: dict[str, str] | None = None,
) -> list[TopicCluster]:
    alias_map = _merge_aliases(aliases)
    buckets: dict[str, _TopicBucket] = {}

    def get_bucket(canonical: str) -> _TopicBucket:
        if canonical not in buckets:
            buckets[canonical] = _TopicBucket(canonical_name=canonical)
        return buckets[canonical]

    for chunk in chunks:
        seen_for_chunk: set[str] = set()
        for raw_topic in _candidate_topics(chunk):
            canonical = normalize_topic_name(raw_topic, alias_map)
            if not canonical or canonical in seen_for_chunk:
                continue
            seen_for_chunk.add(canonical)
            bucket = get_bucket(canonical)
            bucket.record_raw(raw_topic)
            bucket.chunk_ids.add(chunk.id)
            bucket.source_ids.add(chunk.source_id)

    for claim in claims:
        if not _claim_subject_as_topic(claim.subject):
            continue
        canonical = normalize_topic_name(claim.subject, alias_map)
        if not canonical:
            continue
        bucket = get_bucket(canonical)
        bucket.record_raw(claim.subject)
        bucket.claim_ids.add(claim.id)
        bucket.source_ids.update(claim.source_ids)

    now = datetime.now(timezone.utc)
    clusters: list[TopicCluster] = []
    for canonical, bucket in sorted(buckets.items()):
        chunk_count = len(bucket.chunk_ids)
        claim_count = len(bucket.claim_ids)
        if chunk_count < min_chunks and claim_count == 0:
            continue

        chunk_ids = sorted(bucket.chunk_ids)
        claim_ids = sorted(bucket.claim_ids)
        display_name = bucket.display_name()
        clusters.append(
            TopicCluster(
                id=_cluster_id(knowledge_base_id, canonical),
                knowledge_base_id=knowledge_base_id,
                name=display_name,
                aliases=bucket.alias_names(display_name),
                chunk_ids=chunk_ids,
                claim_ids=claim_ids,
                source_ids=sorted(bucket.source_ids),
                summary=None,
                status="active",
                content_hash=_cluster_content_hash(chunk_ids, claim_ids),
                updated_at=now,
            )
        )

    return clusters
