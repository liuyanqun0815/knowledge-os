from typing import NotRequired, TypedDict

from compiler.ports import CompileReport
from evolution.ports import ApplyReport
from knowledge.models import Answer
from retrieval.ports import Hit, RetrievalMode


class IngestState(TypedDict):
    file_path: str
    source_type: str
    source_id: str | None
    replaces_source_id: NotRequired[str | None]
    report: CompileReport | None
    evolve_report: NotRequired[ApplyReport | None]
    error: str | None


class AskState(TypedDict):
    question: str
    session_id: str | None
    normalized_question: str | None
    retrieval_mode: RetrievalMode | None
    hits: list[Hit]
    claim_ids: list[str]
    answer: Answer | None
