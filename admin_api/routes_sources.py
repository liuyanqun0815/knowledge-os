from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, Request, UploadFile

from admin_api.schemas import (
    ClaimListItemResponse,
    SourceResponse,
    SourceUploadResponse,
    ZipUploadItemResponse,
    ZipUploadResponse,
)
from admin_api.source_helpers import build_source_response, filter_sources_by_query
from app.admin_auth import require_admin_token
from app.deps import build_orchestrator_for_request, get_kb_repo
from compiler.enrichment import enrich_source
from infra.upload_utils import ALLOWED_UPLOAD_SUFFIXES, extract_zip_documents
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


def _kb_dir(kb_id: str, request: Request) -> Path:
    settings = request.app.state.settings
    return Path(settings.data_root) / kb_id


def _item_from_dest(kb_dir: Path, dest: Path, report) -> ZipUploadItemResponse:
    try:
        rel = dest.relative_to(kb_dir.resolve())
        relative_path = rel.as_posix()
        directory = f"/{rel.parent.as_posix()}" if rel.parent.parts else "/"
    except ValueError:
        relative_path = dest.name
        directory = "/"

    return ZipUploadItemResponse(
        source_id=report.source_id,
        path=str(dest),
        claims_created=report.claims_created,
        entities_upserted=report.entities_upserted,
        evidence_links=report.evidence_links,
        quarantined=report.quarantined,
        errors=report.errors,
        relative_path=relative_path,
        directory=directory,
    )


def _ingest_saved_file(
    kb_id: str,
    request: Request,
    dest: Path,
    source_type: str,
    replaces_source_id: str | None = None,
):
    orchestrator = build_orchestrator_for_request(kb_id, request)
    try:
        return orchestrator.ingest(str(dest), source_type, replaces_source_id=replaces_source_id)
    except DomainError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _schedule_enrichment(
    kb_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    source_ids: list[str],
) -> None:
    orchestrator = build_orchestrator_for_request(kb_id, request)
    deps = orchestrator.deps
    settings = request.app.state.settings
    llm_enabled = settings.extract_llm and deps.llm_client.is_configured
    for source_id in source_ids:
        if llm_enabled:
            deps.knowledge.update_source_status(source_id, "enriching")
        background_tasks.add_task(
            enrich_source,
            kb_id=kb_id,
            source_id=source_id,
            deps=deps,
            settings=settings,
        )


def _upload_zip_bytes(
    kb_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    kb_dir: Path,
    zip_bytes: bytes,
    source_type: str,
) -> SourceUploadResponse:
    extracted, extract_errors = extract_zip_documents(zip_bytes, kb_dir)

    results: list[ZipUploadItemResponse] = []
    ingest_errors = list(extract_errors)
    for dest in extracted:
        try:
            report = _ingest_saved_file(kb_id, request, dest, source_type)
            results.append(_item_from_dest(kb_dir, dest, report))
        except HTTPException as exc:
            ingest_errors.append(f"{dest.name}: {exc.detail}")

    _schedule_enrichment(kb_id, request, background_tasks, [item.source_id for item in results])
    skipped = len(extracted) - len(results) + len(extract_errors)
    return SourceUploadResponse(
        upload_mode="zip",
        files_total=len(extracted) + len(extract_errors),
        files_ingested=len(results),
        files_skipped=skipped,
        results=results,
        errors=ingest_errors,
    )


def _upload_single_file(
    kb_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    kb_dir: Path,
    dest: Path,
    source_type: str,
    replaces_source_id: str | None = None,
) -> SourceUploadResponse:
    report = _ingest_saved_file(kb_id, request, dest, source_type, replaces_source_id)
    _schedule_enrichment(kb_id, request, background_tasks, [report.source_id])
    item = _item_from_dest(kb_dir, dest, report)
    return SourceUploadResponse(
        upload_mode="single",
        files_total=1,
        files_ingested=1,
        files_skipped=0,
        results=[item],
        errors=list(report.errors),
    )


@router.post("/{kb_id}/sources/upload", response_model=SourceUploadResponse)
async def upload_source(
    kb_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    _: None = Depends(_resolve_active_kb),
    file: UploadFile = File(...),
    source_type: str = Form("policy"),
    replaces_source_id: str | None = Form(None),
) -> SourceUploadResponse:
    filename = Path(file.filename or "").name
    if not filename:
        raise HTTPException(status_code=400, detail="filename is required")

    kb_dir = _kb_dir(kb_id, request)
    kb_dir.mkdir(parents=True, exist_ok=True)
    content = await file.read()

    if filename.lower().endswith(".zip"):
        if replaces_source_id:
            raise HTTPException(status_code=400, detail="replaces_source_id is not supported for zip upload")
        return _upload_zip_bytes(kb_id, request, background_tasks, kb_dir, content, source_type)

    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_UPLOAD_SUFFIXES:
        raise HTTPException(status_code=400, detail=f"unsupported file type: {suffix}")

    dest = kb_dir / filename
    try:
        dest.write_bytes(content)
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"failed to save upload: {exc}") from exc

    return _upload_single_file(
        kb_id,
        request,
        background_tasks,
        kb_dir,
        dest,
        source_type,
        replaces_source_id,
    )


@router.post("/{kb_id}/sources/upload-zip", response_model=ZipUploadResponse, deprecated=True)
async def upload_zip(
    kb_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    _: None = Depends(_resolve_active_kb),
    file: UploadFile = File(...),
    source_type: str = Form("policy"),
) -> ZipUploadResponse:
    filename = Path(file.filename or "").name.lower()
    if not filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="upload-zip requires a .zip file")

    kb_dir = _kb_dir(kb_id, request)
    zip_bytes = await file.read()
    return _upload_zip_bytes(kb_id, request, background_tasks, kb_dir, zip_bytes, source_type)


@router.get("/{kb_id}/sources", response_model=list[SourceResponse])
def list_sources(
    kb_id: str,
    request: Request,
    q: str | None = Query(default=None, description="Fuzzy search by filename, path, or source id"),
    _: None = Depends(_resolve_active_kb),
) -> list[SourceResponse]:
    orchestrator = build_orchestrator_for_request(kb_id, request)
    kb_dir = _kb_dir(kb_id, request)
    payloads = [
        build_source_response(source, orchestrator.deps.knowledge, kb_dir)
        for source in orchestrator.deps.knowledge.list_sources()
    ]
    filtered = filter_sources_by_query(payloads, q)
    filtered.sort(key=lambda item: (item.get("directory", ""), item.get("relative_path", "")))
    return [SourceResponse(**payload) for payload in filtered]


@router.get("/{kb_id}/sources/{source_id}/claims", response_model=list[ClaimListItemResponse])
def list_source_claims(
    kb_id: str,
    source_id: str,
    request: Request,
    _: None = Depends(_resolve_active_kb),
) -> list[ClaimListItemResponse]:
    orchestrator = build_orchestrator_for_request(kb_id, request)
    source = orchestrator.deps.knowledge.get_source(source_id)
    if source is None:
        raise HTTPException(status_code=404, detail=f"source_not_found: {source_id}")

    claims = orchestrator.deps.knowledge.get_claims_for_source(source_id)
    claims_sorted = sorted(claims, key=lambda claim: (claim.subject, claim.predicate, claim.version))
    return [ClaimListItemResponse.from_claim(claim) for claim in claims_sorted]
