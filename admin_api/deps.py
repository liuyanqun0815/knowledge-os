from __future__ import annotations

from fastapi import Depends, HTTPException, Request

from app.admin_auth import require_admin_token
from app.deps import get_kb_repo
from knowledge_base.ports import KnowledgeBasePort


def require_kb_repo(
    request: Request,
    _: None = Depends(require_admin_token),
) -> KnowledgeBasePort:
    repo = get_kb_repo(request)
    if repo is None:
        raise HTTPException(status_code=503, detail="admin knowledge base API requires AKOS_USE_PG=true")
    return repo
