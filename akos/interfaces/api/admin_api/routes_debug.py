from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from akos.interfaces.api.admin_api.routes_sources import _resolve_active_kb
from akos.interfaces.api.admin_api.schemas import DebugAskRequest, DebugAskResponse, GraphNeighborResponse
from akos.interfaces.api.deps import build_orchestrator_for_request
from knowledge.errors import DomainError
from akos.application.ask.service import AskResult

router = APIRouter(prefix="/knowledge-bases", tags=["admin-debug"])


@router.post("/{kb_id}/debug/ask", response_model=DebugAskResponse)
def debug_ask(
    kb_id: str,
    body: DebugAskRequest,
    request: Request,
    _: None = Depends(_resolve_active_kb),
) -> DebugAskResponse:
    orchestrator = build_orchestrator_for_request(kb_id, request)
    try:
        result = orchestrator.ask(
            body.question,
            session_id=body.session_id,
            as_of=body.as_of,
            include_trace=True,
        )
    except DomainError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not isinstance(result, AskResult):
        raise HTTPException(status_code=500, detail="debug ask requires trace")

    answer = result.answer
    return DebugAskResponse(
        text=answer.text,
        claim_ids=answer.claim_ids,
        evidence=answer.evidence,
        confidence=answer.confidence,
        retrieval_mode=answer.retrieval_mode,
        verification_status=answer.verification_status,
        competing_claim_ids=answer.competing_claim_ids,
        procedure_id=answer.procedure_id,
        as_of=answer.as_of,
        trace=result.trace,
        duration_ms=answer.duration_ms,
    )


@router.get("/{kb_id}/debug/graph/{entity_id}/neighbors", response_model=list[GraphNeighborResponse])
def graph_neighbors(
    kb_id: str,
    entity_id: str,
    request: Request,
    predicates: list[str] | None = Query(default=None),
    depth: int = Query(default=1, ge=1, le=3),
    _: None = Depends(_resolve_active_kb),
) -> list[GraphNeighborResponse]:
    orchestrator = build_orchestrator_for_request(kb_id, request)
    edges = orchestrator.deps.graph.neighbors(entity_id, predicates=predicates, depth=depth)
    return [
        GraphNeighborResponse(src=edge.src, predicate=edge.predicate, dst=edge.dst, props=edge.props)
        for edge in edges
    ]
