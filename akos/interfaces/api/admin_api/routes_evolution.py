from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from akos.interfaces.api.admin_api.claim_history import sorted_claim_history
from akos.interfaces.api.admin_api.routes_sources import _resolve_active_kb
from akos.interfaces.api.admin_api.schemas import ClaimHistoryItemResponse, EvolveSourceRequest, EvolveSourceResponse
from akos.interfaces.api.deps import build_orchestrator_for_request
from akos.domain.errors import DomainError

router = APIRouter(prefix="/knowledge-bases", tags=["admin-evolution"])


@router.post("/{kb_id}/sources/{source_id}/evolve", response_model=EvolveSourceResponse)
def evolve_source(
    kb_id: str,
    source_id: str,
    body: EvolveSourceRequest,
    request: Request,
    _: None = Depends(_resolve_active_kb),
) -> EvolveSourceResponse:
    orchestrator = build_orchestrator_for_request(kb_id, request)
    try:
        report = orchestrator.evolve_source(source_id, replaces_source_id=body.replaces_source_id)
    except DomainError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return EvolveSourceResponse.from_report(report)


@router.get("/{kb_id}/claims/{family_id}/history", response_model=list[ClaimHistoryItemResponse])
def claim_history(
    kb_id: str,
    family_id: str,
    request: Request,
    _: None = Depends(_resolve_active_kb),
) -> list[ClaimHistoryItemResponse]:
    orchestrator = build_orchestrator_for_request(kb_id, request)
    claims_sorted = sorted_claim_history(orchestrator.deps.knowledge, family_id)
    return [ClaimHistoryItemResponse.from_claim(claim) for claim in claims_sorted]
