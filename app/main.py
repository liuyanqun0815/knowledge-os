from fastapi import APIRouter, Depends, FastAPI

from admin_api.routes_knowledge_bases import router as knowledge_bases_router
from admin_api.routes_sources import router as sources_router
from app.admin_auth import require_admin_token
from app.routes import router
from infra.settings import Settings


def create_app(data_root: str | None = None) -> FastAPI:
    settings = Settings(data_root=data_root) if data_root is not None else Settings()
    app = FastAPI(title="AKOS", version="0.1.0")
    app.state.settings = settings
    app.state.orchestrator_cache = {}
    app.include_router(router)
    admin_router = APIRouter(dependencies=[Depends(require_admin_token)])
    admin_router.include_router(knowledge_bases_router)
    admin_router.include_router(sources_router)
    app.include_router(admin_router, prefix="/admin")
    return app


app = create_app()
