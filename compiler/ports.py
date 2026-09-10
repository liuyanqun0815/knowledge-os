from dataclasses import dataclass
from typing import Protocol


@dataclass
class ExtractedClaim:
    subject: str
    predicate: str
    object: str
    confidence: float
    quote: str
    start: int
    end: int


@dataclass
class CompileReport:
    source_id: str
    claims_created: int
    entities_upserted: int
    evidence_links: int
    quarantined: int
    errors: list[str]


@dataclass
class ChunkIndexReport:
    source_id: str
    chunks_created: int
    truncated: bool
    errors: list[str]


class ExtractorPort(Protocol):
    def extract(self, text: str) -> list[ExtractedClaim]: ...


class CompilerPort(Protocol):
    def ingest(self, source_id: str, staging: bool = False) -> CompileReport: ...
