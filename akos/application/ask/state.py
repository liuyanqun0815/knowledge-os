from datetime import datetime
from typing import Annotated, NotRequired, TypedDict
import operator

from akos.domain.ports.compiler import CompileReport, ChunkIndexReport
from akos.domain.ports.evolution import ApplyReport
from akos.domain.models.knowledge import Answer
from akos.domain.models.memory import Procedure
from akos.domain.ports.retrieval import Hit, RetrievalMode
from akos.domain.ports.verification import VerificationResult


class IngestState(TypedDict):
    file_path: str
    source_type: str
    source_id: str | None
    replaces_source_id: NotRequired[str | None]
    report: CompileReport | None
    chunk_report: NotRequired[ChunkIndexReport | None]
    chunks_planned: NotRequired[bool]
    verify_report: NotRequired[dict | None]
    evolve_report: NotRequired[ApplyReport | None]
    error: str | None


class AskState(TypedDict):
    question: str
    session_id: str | None
    as_of: datetime | None
    normalized_question: str | None
    recall_episodes: NotRequired[list[dict]]
    retrieval_mode: RetrievalMode | None
    hits: list[Hit]
    chunk_hits: list[Hit]
    wiki_hits: NotRequired[list[Hit]]
    claim_ids: list[str]
    chunk_ids: list[str]
    wiki_pages: NotRequired[list[dict]]
    verification: VerificationResult | None
    synthesis_text: str | None
    synthesis_citations: list[dict]
    synthesis_skipped_reason: str | None
    trace: Annotated[list[dict], operator.add]
    answer: Answer | None
    procedure: Procedure | None
