from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response

from akos.interfaces.api.admin_api.routes_sources import _resolve_active_kb
from akos.interfaces.api.admin_api.schemas import (
    PurgeStaleChunksResponse,
    WikiCompileResponse,
    WikiExportRequest,
    WikiExportResponse,
    WikiPageResponse,
    WikiSearchResponse,
    WikiTreeResponse,
)
from akos.interfaces.api.deps import build_orchestrator_for_request
from infra.bootstrap import build_wiki_compile_deps
from akos.application.wiki.archive import build_wiki_zip
from akos.application.wiki.browser import build_wiki_tree, read_wiki_page, search_wiki_pages
from akos.application.wiki.compile import CompileReport, compile_topics_for_source
from akos.application.wiki.export import export_wiki, resolve_wiki_output_dir
from akos.application.wiki.paths import compile_wiki_root

router = APIRouter(prefix="/knowledge-bases", tags=["admin-wiki"])


@router.get("/{kb_id}/wiki/tree", response_model=WikiTreeResponse)
def get_wiki_tree(kb_id: str, request: Request, _: None = Depends(_resolve_active_kb)) -> WikiTreeResponse:
    settings = request.app.state.settings
    wiki_root = compile_wiki_root(settings.data_root, kb_id)
    if not wiki_root.is_dir():
        return WikiTreeResponse(kb_id=kb_id, wiki_root=str(wiki_root), hubs=[])
    payload = build_wiki_tree(wiki_root)
    return WikiTreeResponse(kb_id=kb_id, wiki_root=str(wiki_root), hubs=payload["hubs"])


@router.get("/{kb_id}/wiki/pages/{page_id:path}", response_model=WikiPageResponse)
def get_wiki_page(
    kb_id: str,
    page_id: str,
    request: Request,
    _: None = Depends(_resolve_active_kb),
) -> WikiPageResponse:
    settings = request.app.state.settings
    wiki_root = compile_wiki_root(settings.data_root, kb_id)
    try:
        payload = read_wiki_page(wiki_root, page_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid_page_id") from None
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="wiki_page_not_found") from None
    return WikiPageResponse(**payload)


@router.get("/{kb_id}/wiki/search", response_model=WikiSearchResponse)
def search_wiki(
    kb_id: str,
    request: Request,
    q: str = Query(""),
    limit: int = Query(50, ge=1, le=100),
    _: None = Depends(_resolve_active_kb),
) -> WikiSearchResponse:
    settings = request.app.state.settings
    wiki_root = compile_wiki_root(settings.data_root, kb_id)
    if not wiki_root.is_dir():
        return WikiSearchResponse(query=q, total=0, hits=[])
    payload = search_wiki_pages(wiki_root, q, limit=limit)
    return WikiSearchResponse(**payload)


@router.get("/{kb_id}/wiki/download")
def download_wiki_zip(
    kb_id: str,
    request: Request,
    _: None = Depends(_resolve_active_kb),
) -> Response:
    settings = request.app.state.settings
    wiki_root = compile_wiki_root(settings.data_root, kb_id)
    if not wiki_root.is_dir():
        raise HTTPException(status_code=404, detail="wiki_not_found")
    try:
        payload = build_wiki_zip(wiki_root)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="wiki_not_found") from exc
    filename = f"{kb_id}-wiki.zip"
    return Response(
        content=payload,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/{kb_id}/wiki/export", response_model=WikiExportResponse)
def export_knowledge_base_wiki(
    kb_id: str,
    request: Request,
    body: WikiExportRequest | None = None,
    _: None = Depends(_resolve_active_kb),
) -> WikiExportResponse:
    orchestrator = build_orchestrator_for_request(kb_id, request)
    settings = request.app.state.settings
    output_dir_arg = body.output_dir if body else None
    try:
        output_dir = resolve_wiki_output_dir(settings.data_root, kb_id, output_dir_arg)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    result = export_wiki(
        orchestrator.deps.knowledge,
        orchestrator.deps.evidence,
        kb_id,
        output_dir,
        use_llm=body.use_llm if body else False,
        llm_client=orchestrator.deps.llm_client,
        settings=settings,
        graph=orchestrator.deps.graph,
    )
    return WikiExportResponse(
        kb_id=result.kb_id,
        output_path=str(result.output_dir),
        files_written=result.files_written,
        source_pages=result.source_pages,
        entity_pages=result.entity_pages,
        topic_pages=result.topic_pages,
        exported_at=result.exported_at,
    )


@router.post("/{kb_id}/wiki/compile", response_model=WikiCompileResponse)
def compile_knowledge_base_wiki(
    kb_id: str,
    request: Request,
    source_id: str | None = Query(default=None),
    _: None = Depends(_resolve_active_kb),
) -> WikiCompileResponse:
    settings = request.app.state.settings
    cache: dict = getattr(request.app.state, "orchestrator_cache", {}) or {}
    existing = cache[kb_id].deps if kb_id in cache else None
    deps = build_wiki_compile_deps(kb_id, settings, existing=existing)
    knowledge = deps.knowledge

    if source_id is not None:
        if knowledge.get_source(source_id) is None:
            raise HTTPException(status_code=404, detail=f"source_not_found: {source_id}")
        source_ids = [source_id]
    else:
        source_ids = [source.id for source in knowledge.list_sources()]

    aggregate = CompileReport()
    compiled_sources: list[str] = []
    for sid in source_ids:
        report = compile_topics_for_source(
            knowledge,
            kb_id,
            sid,
            settings.data_root,
            settings,
            graph=deps.graph,
            llm_client=deps.llm_client,
        )
        if report.pages_written or report.topics:
            compiled_sources.append(sid)
        aggregate.pages_written += report.pages_written
        for topic in report.topics:
            if topic not in aggregate.topics:
                aggregate.topics.append(topic)

    wiki_root = compile_wiki_root(settings.data_root, kb_id)
    wiki_retrieval = deps.wiki_retrieval
    if wiki_retrieval is not None and wiki_root.exists():
        wiki_retrieval.index_wiki_root(wiki_root)

    return WikiCompileResponse(
        kb_id=kb_id,
        wiki_root=str(wiki_root),
        pages_written=aggregate.pages_written,
        topics=aggregate.topics,
        source_ids=compiled_sources or source_ids,
    )


@router.post("/{kb_id}/chunks/purge-stale", response_model=PurgeStaleChunksResponse)
def purge_stale_chunks(
    kb_id: str,
    request: Request,
    source_id: str | None = Query(default=None),
    _: None = Depends(_resolve_active_kb),
) -> PurgeStaleChunksResponse:
    orchestrator = build_orchestrator_for_request(kb_id, request)
    knowledge = orchestrator.deps.knowledge

    if source_id is not None:
        if knowledge.get_source(source_id) is None:
            raise HTTPException(status_code=404, detail=f"source_not_found: {source_id}")
        source_ids = [source_id]
    else:
        source_ids = [source.id for source in knowledge.list_sources()]

    deleted = 0
    sources_purged = 0
    for sid in source_ids:
        count = knowledge.purge_stale_chunks(sid)
        if count:
            sources_purged += 1
        deleted += count

    return PurgeStaleChunksResponse(kb_id=kb_id, deleted=deleted, sources_purged=sources_purged)
