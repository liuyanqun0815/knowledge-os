from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from admin_api.claim_helpers import approve_staging_claim, list_filtered_claims, reject_staging_claim
from admin_api.routes_sources import _resolve_active_kb
from admin_api.schemas import ClaimListItemResponse, RejectStagingClaimResponse
from app.deps import build_orchestrator_for_request
from knowledge.errors import DomainError

router = APIRouter(prefix="/knowledge-bases", tags=["admin-claims"])


@router.get("/{kb_id}/claims", response_model=list[ClaimListItemResponse])
def list_claims(
    kb_id: str,
    request: Request,
    status: str | None = None,
    subject: str | None = None,
    predicate: str | None = None,
    object: str | None = None,
    _: None = Depends(_resolve_active_kb),
) -> list[ClaimListItemResponse]:
    orchestrator = build_orchestrator_for_request(kb_id, request)
    claims = list_filtered_claims(
        orchestrator.deps.knowledge,
        status=status,
        subject=subject,
        predicate=predicate,
        object=object,
    )
    return [ClaimListItemResponse.from_claim(claim) for claim in claims]


@router.post("/{kb_id}/claims/{claim_id}/approve-staging", response_model=ClaimListItemResponse)
def approve_staging(
    kb_id: str,
    claim_id: str,
    request: Request,
    _: None = Depends(_resolve_active_kb),
) -> ClaimListItemResponse:
    orchestrator = build_orchestrator_for_request(kb_id, request)
    try:
        claim = approve_staging_claim(orchestrator.deps, claim_id)
    except DomainError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ClaimListItemResponse.from_claim(claim)


@router.post("/{kb_id}/claims/{claim_id}/reject-staging", response_model=RejectStagingClaimResponse)
def reject_staging(
    kb_id: str,
    claim_id: str,
    request: Request,
    _: None = Depends(_resolve_active_kb),
) -> RejectStagingClaimResponse:
    orchestrator = build_orchestrator_for_request(kb_id, request)
    try:
        claim = reject_staging_claim(orchestrator.deps, claim_id)
    except DomainError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RejectStagingClaimResponse(claim=ClaimListItemResponse.from_claim(claim))
