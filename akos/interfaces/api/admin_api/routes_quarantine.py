from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from akos.interfaces.api.admin_api.claim_helpers import index_approved_claim
from akos.interfaces.api.admin_api.routes_sources import _resolve_active_kb
from akos.interfaces.api.admin_api.schemas import (
    ApproveAllQuarantineFailure,
    ApproveAllQuarantineResponse,
    ApproveQuarantineResponse,
    ClaimListItemResponse,
    QuarantineItemResponse,
)
from akos.interfaces.api.deps import build_orchestrator_for_request
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


@router.post("/{kb_id}/quarantine/approve-all", response_model=ApproveAllQuarantineResponse)
def approve_all_quarantine(
    kb_id: str,
    request: Request,
    _: None = Depends(_resolve_active_kb),
) -> ApproveAllQuarantineResponse:
    orchestrator = build_orchestrator_for_request(kb_id, request)
    knowledge = orchestrator.deps.knowledge
    pending_ids = [item["id"] for item in knowledge.list_quarantine()]

    claims: list[ClaimListItemResponse] = []
    failures: list[ApproveAllQuarantineFailure] = []
    for quarantine_id in pending_ids:
        try:
            claim = knowledge.approve_quarantine(quarantine_id)
        except DomainError as exc:
            failures.append(ApproveAllQuarantineFailure(id=quarantine_id, detail=str(exc)))
            continue
        index_approved_claim(orchestrator.deps, claim)
        claims.append(ClaimListItemResponse.from_claim(claim))

    return ApproveAllQuarantineResponse(
        approved_count=len(claims),
        failed_count=len(failures),
        claims=claims,
        failures=failures,
    )


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
