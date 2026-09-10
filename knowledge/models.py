from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


@dataclass
class Source:
    id: str
    title: str
    type: str
    uri: str
    version: str
    created_at: datetime
    status: str
    replaces_source_id: Optional[str] = None


@dataclass
class Claim:
    id: str
    family_id: str
    version: int
    subject: str
    predicate: str
    object: str
    subject_type: str
    object_type: str
    confidence: float
    status: str
    valid_from: Optional[datetime]
    valid_to: Optional[datetime]
    source_ids: list[str] = field(default_factory=list)


@dataclass
class Event:
    id: str
    type: str
    participants: list[str]
    timestamp: datetime
    source_id: str


@dataclass
class TextSpan:
    source_id: str
    start: int
    end: int
    quote: str


@dataclass
class Answer:
    text: str
    claim_ids: list[str]
    evidence: list[dict[str, Any]]
    confidence: float
    retrieval_mode: str
    verification_status: str = "verified"  # verified | partial | unverified | conflict
    as_of: datetime | None = None
    procedure_id: str | None = None
    competing_claim_ids: list[str] = field(default_factory=list)
    chunk_ids: list[str] = field(default_factory=list)
    chunk_citations: list[dict[str, Any]] = field(default_factory=list)
    synthesis_used: bool = False


@dataclass
class SourceChunk:
    id: str
    source_id: str
    chunk_index: int
    title: str | None
    summary: str | None
    text: str
    start: int
    end: int
    section_path: list[str] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)
    token_count: int = 0
    status: str = "active"
    content_hash: str = ""
    created_at: datetime | None = None
