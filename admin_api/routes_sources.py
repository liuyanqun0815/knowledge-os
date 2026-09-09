from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile

from admin_api.schemas import SourceResponse, UploadSourceResponse
from app.admin_auth import require_admin_token
from app.deps import build_orchestrator_for_request, get_kb_repo
from knowledge.errors import DomainError

router = APIRouter(prefix="/knowledge-bases", tags=["admin-sources"])


def _resolve_active_kb(
    kb_id: str,
    request: Request,
    _: None = Depends(require_admin_token),
) -> None:
    settings = request.app.state.settings
    kb_repo = get_kb_repo(request)
    if settings.use_pg:
        if kb_repo is None:
            raise HTTPException(status_code=503, detail="admin source API requires AKOS_USE_PG=true")
        kb = kb_repo.get(kb_id)
        if kb is None:
            raise HTTPException(status_code=404, detail=f"knowledge_base_not_found: {kb_id}")
        if kb.status != "active":
            raise HTTPException(status_code=400, detail=f"knowledge_base_not_active: {kb_id}")
        return

    try:
        build_orchestrator_for_request(kb_id, request)
    except DomainError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{kb_id}/sources/upload", response_model=UploadSourceResponse)
async def upload_source(
    kb_id: str,
    request: Request,
    _: None = Depends(_resolve_active_kb),
    file: UploadFile = File(...),
    source_type: str = Form("policy"),
    replaces_source_id: str | None = Form(None),
) -> UploadSourceResponse:
    filename = Path(file.filename or "").name
    if not filename:
        raise HTTPException(status_code=400, detail="filename is required")
    suffix = Path(filename).suffix.lower()
    if suffix not in {".md", ".txt"}:
        raise HTTPException(status_code=400, detail=f"unsupported file type: {suffix}")

    settings = request.app.state.settings
    kb_dir = Path(settings.data_root) / kb_id
    kb_dir.mkdir(parents=True, exist_ok=True)
    dest = kb_dir / filename

    content = await file.read()
    try:
        dest.write_bytes(content)
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"failed to save upload: {exc}") from exc

    orchestrator = build_orchestrator_for_request(kb_id, request)
    try:
        report = orchestrator.ingest(str(dest), source_type, replaces_source_id=replaces_source_id)
    except DomainError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return UploadSourceResponse(
        source_id=report.source_id,
        path=str(dest),
        claims_created=report.claims_created,
        entities_upserted=report.entities_upserted,
        evidence_links=report.evidence_links,
        quarantined=report.quarantined,
        errors=report.errors,
    )


@router.get("/{kb_id}/sources", response_model=list[SourceResponse])
def list_sources(
    kb_id: str,
    request: Request,
    _: None = Depends(_resolve_active_kb),
) -> list[SourceResponse]:
    orchestrator = build_orchestrator_for_request(kb_id, request)
    sources = orchestrator.deps.knowledge.list_sources()
    return [
        SourceResponse(
            id=source.id,
            title=source.title,
            type=source.type,
            uri=source.uri,
            version=source.version,
            created_at=source.created_at,
            status=source.status,
        )
        for source in sources
    ]
