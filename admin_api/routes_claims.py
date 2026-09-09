from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from admin_api.claim_helpers import list_filtered_claims
from admin_api.routes_sources import _resolve_active_kb
from admin_api.schemas import ClaimListItemResponse
from app.deps import build_orchestrator_for_request

router = APIRouter(prefix="/knowledge-bases", tags=["admin-claims"])


@router.get("/{kb_id}/claims", response_model=list[ClaimListItemResponse])
def list_claims(
    kb_id: str,
    request: Request,
    status: str | None = None,
    subject: str | None = None,
    _: None = Depends(_resolve_active_kb),
) -> list[ClaimListItemResponse]:
    orchestrator = build_orchestrator_for_request(kb_id, request)
    claims = list_filtered_claims(orchestrator.deps.knowledge, status=status, subject=subject)
    return [ClaimListItemResponse.from_claim(claim) for claim in claims]
