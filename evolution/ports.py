from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from knowledge.models import Claim


@dataclass
class KnowledgeDiff:
    source_old_id: str
    source_new_id: str
    claims_added: list[str] = field(default_factory=list)
    claims_superseded: list[tuple[str, str]] = field(default_factory=list)
    entities_changed: list[str] = field(default_factory=list)
    events: list[str] = field(default_factory=list)


@dataclass
class ApplyReport:
    source_old_id: str
    source_new_id: str
    claims_activated: list[str] = field(default_factory=list)
    claims_superseded: list[str] = field(default_factory=list)
    events_created: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class EvolutionPort(Protocol):
    def diff_sources(self, old_source_id: str, new_source_id: str) -> KnowledgeDiff: ...

    def apply_diff(self, diff: KnowledgeDiff) -> ApplyReport: ...

    def as_of(self, query_time: datetime, claim_family_id: str) -> Claim | None: ...
