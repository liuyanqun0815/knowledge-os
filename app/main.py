from fastapi import FastAPI

from app.routes import router
from infra.settings import Settings


def create_app(data_root: str | None = None) -> FastAPI:
    settings = Settings(data_root=data_root) if data_root is not None else Settings()
    app = FastAPI(title="AKOS", version="0.1.0")
    app.state.settings = settings
    app.state.orchestrator_cache = {}
    app.include_router(router)
    return app


app = create_app()
