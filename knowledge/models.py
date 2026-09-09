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
