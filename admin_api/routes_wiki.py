from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from admin_api.routes_sources import _resolve_active_kb
from admin_api.schemas import WikiExportRequest, WikiExportResponse
from app.deps import build_orchestrator_for_request
from wiki.export import export_wiki, resolve_wiki_output_dir

router = APIRouter(prefix="/knowledge-bases", tags=["admin-wiki"])


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
    )
    return WikiExportResponse(
        kb_id=result.kb_id,
        output_path=str(result.output_dir),
        files_written=result.files_written,
        source_pages=result.source_pages,
        entity_pages=result.entity_pages,
        exported_at=result.exported_at,
    )
