from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from admin_api.claim_helpers import index_approved_claim
from admin_api.routes_sources import _resolve_active_kb
from admin_api.schemas import ApproveQuarantineResponse, ClaimListItemResponse, QuarantineItemResponse
from app.deps import build_orchestrator_for_request
from knowledge.errors import DomainError

router = APIRouter(prefix="/knowledge-bases", tags=["admin-quarantine"])


@router.get("/{kb_id}/quarantine", response_model=list[QuarantineItemResponse])
def list_quarantine(
    kb_id: str,
    request: Request,
    _: None = Depends(_resolve_active_kb),
) -> list[QuarantineItemResponse]:
    orchestrator = build_orchestrator_for_request(kb_id, request)
    items = orchestrator.deps.knowledge.list_quarantine()
    return [QuarantineItemResponse(id=item["id"], reason=item["reason"], raw=item["raw"]) for item in items]


@router.post("/{kb_id}/quarantine/{quarantine_id}/approve", response_model=ApproveQuarantineResponse)
def approve_quarantine(
    kb_id: str,
    quarantine_id: int,
    request: Request,
    _: None = Depends(_resolve_active_kb),
) -> ApproveQuarantineResponse:
    orchestrator = build_orchestrator_for_request(kb_id, request)
    try:
        claim = orchestrator.deps.knowledge.approve_quarantine(quarantine_id)
    except DomainError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    index_approved_claim(orchestrator.deps, claim)
    return ApproveQuarantineResponse(claim=ClaimListItemResponse.from_claim(claim))
