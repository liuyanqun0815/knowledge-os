from datetime import datetime
from typing import Annotated, NotRequired, TypedDict
import operator

from compiler.ports import CompileReport, ChunkIndexReport
from evolution.ports import ApplyReport
from knowledge.models import Answer
from memory.models import Procedure
from retrieval.ports import Hit, RetrievalMode
from verification.ports import VerificationResult


class IngestState(TypedDict):
    file_path: str
    source_type: str
    source_id: str | None
    replaces_source_id: NotRequired[str | None]
    report: CompileReport | None
    chunk_report: NotRequired[ChunkIndexReport | None]
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
