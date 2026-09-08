from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.deps import build_orchestrator_for_request
from knowledge.errors import DomainError

router = APIRouter()


class RegisterSourceRequest(BaseModel):
    knowledge_base_id: str
    path: str
    type: str = "policy"


class RegisterSourceResponse(BaseModel):
    source_id: str


class CompileSourceRequest(BaseModel):
    knowledge_base_id: str


class AskRequest(BaseModel):
    knowledge_base_id: str
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
def register_source(body: RegisterSourceRequest, request: Request) -> RegisterSourceResponse:
    orchestrator = build_orchestrator_for_request(body.knowledge_base_id, request)
    try:
        source_id = orchestrator.register_source(body.path, body.type)
    except DomainError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RegisterSourceResponse(source_id=source_id)


@router.post("/sources/{source_id}/compile")
def compile_source(source_id: str, body: CompileSourceRequest, request: Request) -> dict:
    orchestrator = build_orchestrator_for_request(body.knowledge_base_id, request)
    report = orchestrator.compile_source(source_id)
    return asdict(report)


@router.post("/ask", response_model=AskResponse)
def ask(body: AskRequest, request: Request) -> AskResponse:
    orchestrator = build_orchestrator_for_request(body.knowledge_base_id, request)
    try:
        answer = orchestrator.ask(body.question, session_id=body.session_id)
    except DomainError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return AskResponse(
        text=answer.text,
        claim_ids=answer.claim_ids,
        evidence=answer.evidence,
        confidence=answer.confidence,
        retrieval_mode=answer.retrieval_mode,
    )


@router.get("/claims/{claim_id}/evidence", response_model=EvidenceResponse)
def claim_evidence(claim_id: str, knowledge_base_id: str, request: Request) -> EvidenceResponse:
    orchestrator = build_orchestrator_for_request(knowledge_base_id, request)
    bundle = orchestrator.deps.evidence.explain([claim_id])
    return EvidenceResponse(
        conclusion=bundle.conclusion,
        items=bundle.items,
        confidence=bundle.confidence,
    )
