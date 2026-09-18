"""Admin API：知识库文档（sources）上传、列表与萃取结果查询。

核心入口 ``POST /{kb_id}/sources/upload``：
- ``.md`` / ``.txt``：单文件接收后后台 ingest
- ``.pdf`` / ``.docx`` / ``.doc``：接收后后台抽文本并 ingest
- ``.zip``：解压后批量后台 ingest（保留目录）
- 统一响应 ``SourceUploadResponse``（``upload_mode``: ``single`` | ``zip`` | ``tree``）
- 成功接收返回 HTTP 202，``accepted_async=true``；编译在 BackgroundTasks 中执行

``POST .../upload-zip`` 为兼容别名，已标记 deprecated。
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, Request, Response, UploadFile

from akos.interfaces.api.admin_api.schemas import (
    ClaimListItemResponse,
    SourceChunkResponse,
    DeleteTreeRequest,
    DeleteTreeResponse,
    MoveSourcesRequest,
    SourceContentResponse,
    SourceResponse,
    SourceUploadResponse,
    ZipUploadItemResponse,
    ZipUploadResponse,
)
from akos.interfaces.api.admin_api.source_cleanup import purge_source_side_effects, sole_source_claims
from akos.interfaces.api.admin_api.source_helpers import build_source_response, filter_sources_by_query
from akos.interfaces.api.admin_api.upload_jobs import pending_item_response, process_uploaded_source, register_pending_source
from akos.interfaces.api.admin_auth import require_admin_token
from akos.interfaces.api.deps import build_orchestrator_for_request, get_kb_repo, get_knowledge_for_request
from infra.upload_utils import ALLOWED_UPLOAD_SUFFIXES, extract_zip_documents, safe_target_under_kb
from akos.domain.errors import DomainError
from akos.domain.models.knowledge import Source

router = APIRouter(prefix="/knowledge-bases", tags=["admin-sources"])

_ACCEPT_SUMMARY = "已接收，后台编译中"


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


def _safe_target(kb_dir: Path, relative_path: str) -> Path:
    try:
        return safe_target_under_kb(kb_dir, relative_path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _prune_empty_parents(path: Path, kb_dir: Path) -> None:
    current = path.parent
    kb_resolved = kb_dir.resolve()
    while current != kb_resolved and current.is_relative_to(kb_resolved):
        try:
            current.rmdir()
        except OSError:
            break
        current = current.parent


def _schedule_upload_processing(
    kb_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    kb_dir: Path,
    originals: list[Path],
    source_type: str,
    replaces_source_id: str | None = None,
    subject_bind_mode: str | None = None,
) -> list[ZipUploadItemResponse]:
    orchestrator = build_orchestrator_for_request(kb_id, request)
    settings = request.app.state.settings
    results: list[ZipUploadItemResponse] = []
    single = len(originals) == 1
    for original in originals:
        source = register_pending_source(
            knowledge=orchestrator.deps.knowledge,
            kb_dir=kb_dir,
            original=original,
            source_type=source_type,
            replaces_source_id=replaces_source_id if single else None,
        )
        results.append(pending_item_response(kb_dir, original, source.id))
        background_tasks.add_task(
            process_uploaded_source,
            kb_id=kb_id,
            kb_dir=kb_dir,
            original=original,
            source_type=source_type,
            deps=orchestrator.deps,
            settings=settings,
            orchestrator=orchestrator,
            replaces_source_id=replaces_source_id if single else None,
            subject_bind_mode=subject_bind_mode,
        )
    return results


def _async_upload_response(
    *,
    upload_mode: str,
    files_total: int,
    results: list[ZipUploadItemResponse],
    errors: list[str] | None = None,
) -> SourceUploadResponse:
    error_list = list(errors or [])
    return SourceUploadResponse(
        upload_mode=upload_mode,
        files_total=files_total,
        files_ingested=0,
        files_skipped=files_total - len(results),
        results=results,
        errors=error_list,
        ingest_summary=_ACCEPT_SUMMARY,
        accepted_async=True,
    )


def _upload_zip_bytes(
    kb_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    kb_dir: Path,
    zip_bytes: bytes,
    source_type: str,
    subject_bind_mode: str | None = None,
) -> SourceUploadResponse:
    extracted, extract_errors = extract_zip_documents(zip_bytes, kb_dir)
    results = _schedule_upload_processing(
        kb_id,
        request,
        background_tasks,
        kb_dir,
        extracted,
        source_type,
        subject_bind_mode=subject_bind_mode,
    )
    return _async_upload_response(
        upload_mode="zip",
        files_total=len(extracted) + len(extract_errors),
        results=results,
        errors=list(extract_errors),
    )


@router.post("/{kb_id}/sources/upload", response_model=SourceUploadResponse, status_code=202)
async def upload_source(
    kb_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    _: None = Depends(_resolve_active_kb),
    file: UploadFile = File(...),
    source_type: str = Form("policy"),
    replaces_source_id: str | None = Form(None),
    relative_path: str | None = Form(None),
    subject_bind_mode: str | None = Form(None),
) -> SourceUploadResponse:
    """统一上传：按扩展名分流单文件或 ZIP；ZIP 须在 suffix 白名单校验之前处理。"""
    filename = Path(file.filename or "").name
    if not filename:
        raise HTTPException(status_code=400, detail="filename is required")

    kb_dir = _kb_dir(kb_id, request)
    kb_dir.mkdir(parents=True, exist_ok=True)
    content = await file.read()

    # ZIP 单独处理（白名单含 md/txt/pdf/docx/doc）
    if filename.lower().endswith(".zip"):
        if replaces_source_id or relative_path:
            raise HTTPException(
                status_code=400,
                detail="replaces_source_id and relative_path are not supported for zip upload",
            )
        return _upload_zip_bytes(
            kb_id,
            request,
            background_tasks,
            kb_dir,
            content,
            source_type,
            subject_bind_mode=subject_bind_mode,
        )

    target_relative_path = relative_path or filename
    suffix = Path(target_relative_path).suffix.lower()
    if suffix not in ALLOWED_UPLOAD_SUFFIXES:
        raise HTTPException(status_code=400, detail=f"unsupported file type: {suffix}")

    dest = _safe_target(kb_dir, target_relative_path)
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(content)
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"failed to save upload: {exc}") from exc

    results = _schedule_upload_processing(
        kb_id,
        request,
        background_tasks,
        kb_dir,
        [dest],
        source_type,
        replaces_source_id,
        subject_bind_mode=subject_bind_mode,
    )
    return _async_upload_response(upload_mode="single", files_total=1, results=results)


@router.post("/{kb_id}/sources/upload-tree", response_model=SourceUploadResponse, status_code=202)
async def upload_tree(
    kb_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    _: None = Depends(_resolve_active_kb),
    files: list[UploadFile] = File(...),
    relative_paths: list[str] = Form(...),
    source_type: str = Form("policy"),
    subject_bind_mode: str | None = Form(None),
) -> SourceUploadResponse:
    if len(files) != len(relative_paths):
        raise HTTPException(status_code=400, detail="files and relative_paths must have matching lengths")

    kb_dir = _kb_dir(kb_id, request)
    kb_dir.mkdir(parents=True, exist_ok=True)
    # Phase 1: validate all paths/suffixes before any write (no orphan files on mid-batch 400)
    pending: list[tuple[UploadFile, Path]] = []
    for file, relative_path in zip(files, relative_paths):
        destination = _safe_target(kb_dir, relative_path)
        suffix = destination.suffix.lower()
        if suffix not in ALLOWED_UPLOAD_SUFFIXES:
            raise HTTPException(status_code=400, detail=f"unsupported file type: {suffix}")
        pending.append((file, destination))

    # Phase 2: write then schedule
    destinations: list[Path] = []
    errors: list[str] = []
    for file, destination in pending:
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(await file.read())
            destinations.append(destination)
        except OSError as exc:
            errors.append(f"{destination.name}: failed to save upload: {exc}")

    results = _schedule_upload_processing(
        kb_id,
        request,
        background_tasks,
        kb_dir,
        destinations,
        source_type,
        subject_bind_mode=subject_bind_mode,
    )
    return _async_upload_response(
        upload_mode="tree",
        files_total=len(files),
        results=results,
        errors=errors,
    )


@router.post("/{kb_id}/sources/upload-zip", response_model=ZipUploadResponse, status_code=202, deprecated=True)
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
    kb_dir.mkdir(parents=True, exist_ok=True)
    zip_bytes = await file.read()
    return _upload_zip_bytes(kb_id, request, background_tasks, kb_dir, zip_bytes, source_type)


@router.get("/{kb_id}/sources", response_model=list[SourceResponse])
def list_sources(
    kb_id: str,
    request: Request,
    q: str | None = Query(default=None, description="Fuzzy search by filename, path, or source id"),
    _: None = Depends(_resolve_active_kb),
) -> list[SourceResponse]:
    knowledge = get_knowledge_for_request(kb_id, request)
    kb_dir = _kb_dir(kb_id, request)
    payloads = [build_source_response(source, knowledge, kb_dir) for source in knowledge.list_sources()]
    filtered = filter_sources_by_query(payloads, q)
    filtered.sort(key=lambda item: (item.get("directory", ""), item.get("relative_path", "")))
    return [SourceResponse(**payload) for payload in filtered]


@router.post("/{kb_id}/sources/move", response_model=list[SourceResponse])
def move_sources(
    kb_id: str,
    body: MoveSourcesRequest,
    request: Request,
    _: None = Depends(_resolve_active_kb),
) -> list[SourceResponse]:
    source_is_directory = body.from_path.replace("\\", "/").endswith("/")
    target_is_directory = body.to_path.replace("\\", "/").endswith("/")
    if source_is_directory != target_is_directory:
        raise HTTPException(status_code=400, detail="source and target paths must both be files or directories")

    knowledge = get_knowledge_for_request(kb_id, request)
    kb_dir = _kb_dir(kb_id, request)
    from_target = _safe_target(kb_dir, body.from_path)
    to_target = _safe_target(kb_dir, body.to_path)
    from_relative = from_target.relative_to(kb_dir.resolve()).as_posix()
    to_relative = to_target.relative_to(kb_dir.resolve()).as_posix()
    if source_is_directory and (to_relative == from_relative or to_relative.startswith(f"{from_relative}/")):
        raise HTTPException(status_code=400, detail="cannot move a directory into itself")

    moves: list[tuple[Source, Path, Path]] = []
    for source in knowledge.list_sources():
        payload = build_source_response(source, knowledge, kb_dir)
        relative_path = payload["relative_path"]
        if source_is_directory:
            prefix = f"{from_relative}/"
            if not relative_path.startswith(prefix):
                continue
            suffix = relative_path.removeprefix(prefix)
            destination = _safe_target(kb_dir, f"{to_relative}/{suffix}")
        elif relative_path == from_relative:
            destination = to_target
        else:
            continue
        moves.append((source, _safe_target(kb_dir, relative_path), destination))

    if not moves:
        raise HTTPException(status_code=404, detail=f"source_path_not_found: {body.from_path}")
    source_paths = {source_path for _, source_path, _ in moves}
    destinations = [destination for _, _, destination in moves]
    if len(set(destinations)) != len(destinations) or any(
        destination.exists() and destination not in source_paths for destination in destinations
    ):
        raise HTTPException(status_code=409, detail=f"target_conflict: {body.to_path}")

    moved: list[SourceResponse] = []
    for source, source_path, destination in moves:
        destination.parent.mkdir(parents=True, exist_ok=True)
        source_path.replace(destination)
        _prune_empty_parents(source_path, kb_dir)
        source.title = destination.name
        source.uri = f"file://{destination.resolve()}"
        knowledge.save_source(source)
        moved.append(SourceResponse(**build_source_response(source, knowledge, kb_dir)))
    moved.sort(key=lambda item: item.relative_path)
    return moved


@router.get("/{kb_id}/sources/{source_id}/chunks", response_model=list[SourceChunkResponse])
def list_source_chunks(
    kb_id: str,
    source_id: str,
    request: Request,
    status: str = Query(default="active"),
    _: None = Depends(_resolve_active_kb),
) -> list[SourceChunkResponse]:
    knowledge = get_knowledge_for_request(kb_id, request)
    source = knowledge.get_source(source_id)
    if source is None:
        raise HTTPException(status_code=404, detail=f"source_not_found: {source_id}")

    if status == "all":
        chunks = knowledge.list_chunks(source_id, status="active") + knowledge.list_chunks(source_id, status="stale")
        chunks.sort(key=lambda chunk: chunk.chunk_index)
    elif status in {"active", "stale"}:
        chunks = knowledge.list_chunks(source_id, status=status)
    else:
        raise HTTPException(status_code=400, detail=f"unsupported chunk status filter: {status}")
    return [SourceChunkResponse.from_chunk(chunk) for chunk in chunks]


@router.get("/{kb_id}/sources/{source_id}/claims", response_model=list[ClaimListItemResponse])
def list_source_claims(
    kb_id: str,
    source_id: str,
    request: Request,
    _: None = Depends(_resolve_active_kb),
) -> list[ClaimListItemResponse]:
    knowledge = get_knowledge_for_request(kb_id, request)
    source = knowledge.get_source(source_id)
    if source is None:
        raise HTTPException(status_code=404, detail=f"source_not_found: {source_id}")

    claims = knowledge.get_claims_for_source(source_id)
    claims_sorted = sorted(claims, key=lambda claim: (claim.subject, claim.predicate, claim.version))
    return [ClaimListItemResponse.from_claim(claim) for claim in claims_sorted]


@router.get("/{kb_id}/sources/{source_id}/content", response_model=SourceContentResponse)
def get_source_content(
    kb_id: str,
    source_id: str,
    request: Request,
    _: None = Depends(_resolve_active_kb),
) -> SourceContentResponse:
    knowledge = get_knowledge_for_request(kb_id, request)
    source = knowledge.get_source(source_id)
    if source is None:
        raise HTTPException(status_code=404, detail=f"source_not_found: {source_id}")

    kb_dir = _kb_dir(kb_id, request)
    payload = build_source_response(source, knowledge, kb_dir)
    relative_path = payload.get("relative_path") or ""
    if not relative_path:
        raise HTTPException(status_code=404, detail=f"source_file_not_found: {source_id}")

    source_path = _safe_target(kb_dir, relative_path)
    if not source_path.is_file():
        raise HTTPException(status_code=404, detail=f"source_file_not_found: {source_id}")

    size_bytes = source_path.stat().st_size
    max_bytes = request.app.state.settings.source_content_max_bytes
    if size_bytes > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"source_content_too_large: {size_bytes} > {max_bytes}",
        )

    try:
        content = source_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="source_content_not_utf8") from exc

    return SourceContentResponse(
        source_id=source.id,
        title=source.title,
        relative_path=relative_path,
        content=content,
        size_bytes=size_bytes,
        encoding="utf-8",
    )


@router.delete("/{kb_id}/sources/{source_id}", status_code=204)
def delete_source(
    kb_id: str,
    source_id: str,
    request: Request,
    _: None = Depends(_resolve_active_kb),
) -> Response:
    orchestrator = build_orchestrator_for_request(kb_id, request)
    knowledge = orchestrator.deps.knowledge
    source = knowledge.get_source(source_id)
    if source is None:
        raise HTTPException(status_code=404, detail=f"source_not_found: {source_id}")

    kb_dir = _kb_dir(kb_id, request)
    payload = build_source_response(source, knowledge, kb_dir)
    source_path = _safe_target(kb_dir, payload["relative_path"])
    try:
        source_path.unlink(missing_ok=True)
        _prune_empty_parents(source_path, kb_dir)
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"failed to delete source file: {exc}") from exc
    claims_to_purge = sole_source_claims(knowledge, source_id)
    knowledge.delete_source(source_id)
    purge_source_side_effects(orchestrator.deps, source_id, sole_claims=claims_to_purge)
    return Response(status_code=204)


@router.post("/{kb_id}/sources/delete-tree", response_model=DeleteTreeResponse)
def delete_tree(
    kb_id: str,
    body: DeleteTreeRequest,
    request: Request,
    _: None = Depends(_resolve_active_kb),
) -> DeleteTreeResponse:
    is_directory = body.path.replace("\\", "/").endswith("/")
    orchestrator = build_orchestrator_for_request(kb_id, request)
    knowledge = orchestrator.deps.knowledge
    kb_dir = _kb_dir(kb_id, request)
    target = _safe_target(kb_dir, body.path)
    target_relative = target.relative_to(kb_dir.resolve()).as_posix()

    matches = []
    for source in knowledge.list_sources():
        payload = build_source_response(source, knowledge, kb_dir)
        relative_path = payload["relative_path"]
        if relative_path == target_relative or (is_directory and relative_path.startswith(f"{target_relative}/")):
            matches.append((source, _safe_target(kb_dir, relative_path)))
    if not matches:
        raise HTTPException(status_code=404, detail=f"source_path_not_found: {body.path}")

    for source, source_path in matches:
        try:
            source_path.unlink(missing_ok=True)
            _prune_empty_parents(source_path, kb_dir)
        except OSError as exc:
            raise HTTPException(status_code=500, detail=f"failed to delete source file: {exc}") from exc
        claims_to_purge = sole_source_claims(knowledge, source.id)
        knowledge.delete_source(source.id)
        purge_source_side_effects(orchestrator.deps, source.id, sole_claims=claims_to_purge)
    return DeleteTreeResponse(deleted_count=len(matches))
