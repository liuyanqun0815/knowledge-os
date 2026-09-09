import logging
from contextlib import asynccontextmanager

from fastapi import APIRouter, Depends, FastAPI

from admin_api.routes_claims import router as claims_router
from admin_api.routes_debug import router as debug_router
from admin_api.routes_evolution import router as evolution_router
from admin_api.routes_knowledge_bases import router as knowledge_bases_router
from admin_api.routes_quarantine import router as quarantine_router
from admin_api.routes_sources import router as sources_router
from app.admin_auth import require_admin_token
from app.routes import router
from compiler.enrichment import enrich_source
from infra.bootstrap import _get_kb_repo, build_orchestrator_for_kb
from infra.settings import Settings

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
            cache[knowledge_base.id] = build_orchestrator_for_kb(knowledge_base.id)
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
                logger.exception("Failed to resume enrichment for source %s in knowledge base %s", source.id, kb_id)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _resume_enriching_sources(app)
    yield


def create_app(data_root: str | None = None) -> FastAPI:
    settings = Settings(data_root=data_root) if data_root is not None else Settings()
    app = FastAPI(title="AKOS", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.orchestrator_cache = {}
    app.include_router(router)
    admin_router = APIRouter(dependencies=[Depends(require_admin_token)])
    admin_router.include_router(knowledge_bases_router)
    admin_router.include_router(sources_router)
    admin_router.include_router(claims_router)
    admin_router.include_router(quarantine_router)
    admin_router.include_router(evolution_router)
    admin_router.include_router(debug_router)
    app.include_router(admin_router, prefix="/admin")
    return app


app = create_app()
