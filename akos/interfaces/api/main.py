import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.responses import JSONResponse

from akos.adapters.llm.client import LlmCallError, LlmConfigError, ensure_llm_settings

from akos.interfaces.api.admin_api.routes_claims import router as claims_router
from akos.interfaces.api.admin_api.routes_debug import router as debug_router
from akos.interfaces.api.admin_api.routes_graph import router as graph_router
from akos.interfaces.api.admin_api.routes_evolution import router as evolution_router
from akos.interfaces.api.admin_api.routes_knowledge_bases import router as knowledge_bases_router
from akos.interfaces.api.admin_api.routes_lint import router as lint_router
from akos.interfaces.api.admin_api.routes_wiki import router as wiki_router
from akos.interfaces.api.admin_api.routes_quarantine import router as quarantine_router
from akos.interfaces.api.admin_api.routes_sources import router as sources_router
from akos.interfaces.api.admin_api.routes_topics import router as topics_router
from akos.interfaces.api.admin_auth import require_admin_token
from akos.interfaces.api.routes import router
from akos.interfaces.api.admin_api.upload_jobs import resume_incomplete_uploads
from akos.application.ingest.enrichment import enrich_source
from akos.bootstrap import _get_kb_repo, build_orchestrator_for_kb
from infra.schema_bootstrap import ensure_pg_schema
from infra.settings import Settings
from infra.tracing import configure_langsmith

logger = logging.getLogger(__name__)


def _load_orchestrators_for_resume(app: FastAPI) -> dict:
    cache = app.state.orchestrator_cache
    settings = app.state.settings
    if not settings.use_pg:
        return cache

    kb_repo = _get_kb_repo(settings)
    if kb_repo is None:
        return cache
    for knowledge_base in kb_repo.list():
        if knowledge_base.status == "active" and knowledge_base.id not in cache:
            cache[knowledge_base.id] = build_orchestrator_for_kb(knowledge_base.id, settings=settings)
    return cache


def _resume_enriching_sources(app: FastAPI) -> None:
    settings = app.state.settings
    for kb_id, orchestrator in _load_orchestrators_for_resume(app).items():
        for source in orchestrator.deps.knowledge.list_sources():
            if source.status != "enriching":
                continue
            try:
                enrich_source(
                    kb_id=kb_id,
                    source_id=source.id,
                    deps=orchestrator.deps,
                    settings=settings,
                )
            except Exception:
                logger.exception("恢复 enrich 失败 source=%s kb=%s", source.id, kb_id)


def _resume_background_source_jobs(app: FastAPI) -> None:
    _load_orchestrators_for_resume(app)
    resume_incomplete_uploads(app)
    _resume_enriching_sources(app)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_langsmith(app.state.settings)
    if app.state.settings.use_pg:
        ensure_pg_schema(app.state.settings)
    resume_task = asyncio.create_task(asyncio.to_thread(_resume_background_source_jobs, app))
    try:
        yield
    finally:
        if not resume_task.done():
            resume_task.cancel()
            try:
                await resume_task
            except asyncio.CancelledError:
                pass
            except Exception:
                logger.exception("关闭时后台恢复 source 任务失败")


def create_app(data_root: str | None = None, *, validate_llm: bool = True) -> FastAPI:
    settings = Settings(data_root=data_root) if data_root is not None else Settings()
    if validate_llm:
        ensure_llm_settings(settings)
    configure_langsmith(settings)
    app = FastAPI(title="AKOS", version="0.1.0", lifespan=lifespan)

    @app.exception_handler(LlmConfigError)
    async def _llm_config_error_handler(_request: Request, exc: LlmConfigError) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    @app.exception_handler(LlmCallError)
    async def _llm_call_error_handler(_request: Request, exc: LlmCallError) -> JSONResponse:
        return JSONResponse(status_code=502, content={"detail": str(exc)})
    app.state.settings = settings
    app.state.orchestrator_cache = {}
    app.include_router(router)
    admin_router = APIRouter(dependencies=[Depends(require_admin_token)])
    admin_router.include_router(knowledge_bases_router)
    admin_router.include_router(sources_router)
    admin_router.include_router(claims_router)
    admin_router.include_router(quarantine_router)
    admin_router.include_router(lint_router)
    admin_router.include_router(wiki_router)
    admin_router.include_router(topics_router)
    admin_router.include_router(evolution_router)
    admin_router.include_router(debug_router)
    admin_router.include_router(graph_router)
    app.include_router(admin_router, prefix="/admin")
    return app


app = create_app()
