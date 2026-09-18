from dataclasses import asdict
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from akos.interfaces.api.admin_api.claim_history import sorted_claim_history
from akos.interfaces.api.admin_api.schemas import ClaimHistoryItemResponse
from akos.interfaces.api.admin_auth import require_admin_token
from akos.interfaces.api.deps import build_orchestrator_for_request
from knowledge.errors import DomainError
from akos.application.ask.service import AskResult, LangGraphOrchestrator

router = APIRouter()


class RegisterSourceRequest(BaseModel):
    knowledge_base_id: str
    path: str
    type: str = "policy"
    replaces_source_id: str | None = None


class RegisterSourceResponse(BaseModel):
    source_id: str


class CompileSourceRequest(BaseModel):
    knowledge_base_id: str


class AskRequest(BaseModel):
    knowledge_base_id: str
    question: str
    session_id: str | None = None
    as_of: datetime | None = None
    include_trace: bool = False


class AskResponse(BaseModel):
    text: str
    claim_ids: list[str]
    evidence: list[dict]
    confidence: float
    retrieval_mode: str
    verification_status: str = "verified"
    competing_claim_ids: list[str] = []
    procedure_id: str | None = None
    as_of: datetime | None = None
    request_id: str | None = None
    duration_ms: int | None = None
    trace: list[dict] | None = None


class EvidenceResponse(BaseModel):
    conclusion: str
    items: list[dict]
    confidence: float


def get_ask_orchestrator(body: AskRequest, request: Request) -> LangGraphOrchestrator:
    return build_orchestrator_for_request(body.knowledge_base_id, request)


@router.post("/sources", response_model=RegisterSourceResponse)
def register_source(body: RegisterSourceRequest, request: Request) -> RegisterSourceResponse:
    orchestrator = build_orchestrator_for_request(body.knowledge_base_id, request)
    try:
        source_id = orchestrator.register_source(
            body.path,
            body.type,
            replaces_source_id=body.replaces_source_id,
        )
    except DomainError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RegisterSourceResponse(source_id=source_id)


@router.post("/sources/{source_id}/compile")
def compile_source(source_id: str, body: CompileSourceRequest, request: Request) -> dict:
    orchestrator = build_orchestrator_for_request(body.knowledge_base_id, request)
    report = orchestrator.compile_source(source_id)
    return asdict(report)


@router.post("/ask", response_model=AskResponse, dependencies=[Depends(require_admin_token)])
def ask(
    body: AskRequest,
    include_trace: bool | None = Query(default=None),
    orchestrator: LangGraphOrchestrator = Depends(get_ask_orchestrator),
) -> AskResponse:
    want_trace = include_trace if include_trace is not None else body.include_trace
    try:
        result = orchestrator.ask(
            body.question,
            session_id=body.session_id,
            as_of=body.as_of,
            include_trace=want_trace,
        )
    except DomainError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if isinstance(result, AskResult):
        answer = result.answer
        trace = result.trace
    else:
        answer = result
        trace = None
    return AskResponse(
        text=answer.text,
        claim_ids=answer.claim_ids,
        evidence=answer.evidence,
        confidence=answer.confidence,
        retrieval_mode=answer.retrieval_mode,
        verification_status=answer.verification_status,
        competing_claim_ids=answer.competing_claim_ids,
        procedure_id=answer.procedure_id,
        as_of=answer.as_of,
        request_id=None,
        duration_ms=getattr(answer, "duration_ms", None),
        trace=trace if want_trace else None,
    )


@router.get("/claims/{family_id}/history", response_model=list[ClaimHistoryItemResponse])
def claim_history(family_id: str, knowledge_base_id: str, request: Request) -> list[ClaimHistoryItemResponse]:
    orchestrator = build_orchestrator_for_request(knowledge_base_id, request)
    claims_sorted = sorted_claim_history(orchestrator.deps.knowledge, family_id)
    return [ClaimHistoryItemResponse.from_claim(claim) for claim in claims_sorted]


@router.get("/claims/{claim_id}/evidence", response_model=EvidenceResponse)
def claim_evidence(claim_id: str, knowledge_base_id: str, request: Request) -> EvidenceResponse:
    orchestrator = build_orchestrator_for_request(knowledge_base_id, request)
    bundle = orchestrator.deps.evidence.explain([claim_id])
    return EvidenceResponse(
        conclusion=bundle.conclusion,
        items=bundle.items,
        confidence=bundle.confidence,
    )
