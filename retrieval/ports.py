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
    claim_id: str | None
    score: float
    snippet: str | None
    entity_id: str | None = None


class RetrievalPort(Protocol):
    def index_claim(self, claim: Claim) -> None: ...
    def search(self, query: str, mode: RetrievalMode, filters: dict) -> list[Hit]: ...
