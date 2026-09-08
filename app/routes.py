from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.deps import get_orchestrator
from knowledge.errors import DomainError
from orchestrator.service import LangGraphOrchestrator

router = APIRouter()


class RegisterSourceRequest(BaseModel):
    path: str
    type: str = "policy"


class RegisterSourceResponse(BaseModel):
    source_id: str


class AskRequest(BaseModel):
    question: str
    session_id: str | None = None


class AskResponse(BaseModel):
    text: str
    claim_ids: list[str]
    evidence: list[dict]
    confidence: float
    retrieval_mode: str


class EvidenceResponse(BaseModel):
    conclusion: str
    items: list[dict]
    confidence: float


@router.post("/sources", response_model=RegisterSourceResponse)
def register_source(
    body: RegisterSourceRequest,
    orchestrator: LangGraphOrchestrator = Depends(get_orchestrator),
) -> RegisterSourceResponse:
    try:
        source_id = orchestrator.register_source(body.path, body.type)
    except DomainError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RegisterSourceResponse(source_id=source_id)


@router.post("/sources/{source_id}/compile")
def compile_source(
    source_id: str,
    orchestrator: LangGraphOrchestrator = Depends(get_orchestrator),
) -> dict:
    report = orchestrator.compile_source(source_id)
    return asdict(report)


@router.post("/ask", response_model=AskResponse)
def ask(
    body: AskRequest,
    orchestrator: LangGraphOrchestrator = Depends(get_orchestrator),
) -> AskResponse:
    answer = orchestrator.ask(body.question, session_id=body.session_id)
    return AskResponse(
        text=answer.text,
        claim_ids=answer.claim_ids,
        evidence=answer.evidence,
        confidence=answer.confidence,
        retrieval_mode=answer.retrieval_mode,
    )


@router.get("/claims/{claim_id}/evidence", response_model=EvidenceResponse)
def claim_evidence(
    claim_id: str,
    orchestrator: LangGraphOrchestrator = Depends(get_orchestrator),
) -> EvidenceResponse:
    bundle = orchestrator.deps.evidence.explain([claim_id])
    return EvidenceResponse(
        conclusion=bundle.conclusion,
        items=bundle.items,
        confidence=bundle.confidence,
    )
