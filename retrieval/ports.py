from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from knowledge.models import Claim


class RetrievalMode(str, Enum):
    VECTOR = "VECTOR"
    BM25 = "BM25"
    GRAPH = "GRAPH"
    CLAIM = "CLAIM"
    HYBRID = "HYBRID"


@dataclass
class Hit:
    score: float
    snippet: str | None
    hit_type: str = "claim"
    claim_id: str | None = None
    chunk_id: str | None = None
    source_id: str | None = None
    entity_id: str | None = None
    # Wiki topic-page hits (ref_type alias via hit_type="wiki")
    ref_id: str | None = None
    title: str | None = None
    path: str | None = None


class RetrievalPort(Protocol):
    def index_claim(self, claim: Claim) -> None: ...
    def warm_index(self) -> None: ...
    def search(self, query: str, mode: RetrievalMode, filters: dict) -> list[Hit]: ...
