from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from admin_api.deps import require_kb_repo
from admin_api.schemas import (
    CreateKnowledgeBaseRequest,
    KnowledgeBaseResponse,
    PatchKnowledgeBaseRequest,
)
from knowledge.errors import DomainError
from knowledge_base.ports import KnowledgeBasePort

router = APIRouter(prefix="/knowledge-bases", tags=["admin-knowledge-bases"])


@router.post("", response_model=KnowledgeBaseResponse, status_code=201)
def create_knowledge_base(
    body: CreateKnowledgeBaseRequest,
    kb_repo: KnowledgeBasePort = Depends(require_kb_repo),
) -> KnowledgeBaseResponse:
    try:
        kb = kb_repo.create(name=body.name, domain_type=body.domain_type, description=body.description)
    except DomainError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return KnowledgeBaseResponse.from_model(kb)


@router.get("", response_model=list[KnowledgeBaseResponse])
def list_knowledge_bases(
    include_archived: bool = False,
    kb_repo: KnowledgeBasePort = Depends(require_kb_repo),
) -> list[KnowledgeBaseResponse]:
    items = kb_repo.list(include_archived=include_archived)
    return [KnowledgeBaseResponse.from_model(kb) for kb in items]


@router.get("/{kb_id}", response_model=KnowledgeBaseResponse)
def get_knowledge_base(
    kb_id: str,
    kb_repo: KnowledgeBasePort = Depends(require_kb_repo),
) -> KnowledgeBaseResponse:
    kb = kb_repo.get(kb_id)
    if kb is None:
        raise HTTPException(status_code=404, detail=f"knowledge_base_not_found: {kb_id}")
    return KnowledgeBaseResponse.from_model(kb)


@router.patch("/{kb_id}", response_model=KnowledgeBaseResponse)
def patch_knowledge_base(
    kb_id: str,
    body: PatchKnowledgeBaseRequest,
    request: Request,
    kb_repo: KnowledgeBasePort = Depends(require_kb_repo),
) -> KnowledgeBaseResponse:
    existing = kb_repo.get(kb_id)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"knowledge_base_not_found: {kb_id}")

    if body.status == "archived":
        archived = kb_repo.archive(kb_id)
        if archived is None:
            raise HTTPException(status_code=404, detail=f"knowledge_base_not_found: {kb_id}")
        request.app.state.orchestrator_cache.pop(kb_id, None)
        return KnowledgeBaseResponse.from_model(archived)

    if body.status is not None and body.status != existing.status:
        raise HTTPException(status_code=400, detail=f"unsupported status transition: {body.status}")

    updated = kb_repo.update(
        kb_id,
        name=body.name,
        domain_type=body.domain_type,
        description=body.description,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail=f"knowledge_base_not_found: {kb_id}")
    return KnowledgeBaseResponse.from_model(updated)
