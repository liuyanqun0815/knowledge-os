from fastapi import HTTPException, Request

from infra.bootstrap import build_orchestrator_for_kb
from orchestrator.service import LangGraphOrchestrator


def build_orchestrator_for_request(knowledge_base_id: str, request: Request) -> LangGraphOrchestrator:
    kb_repo = get_kb_repo(request)
    if kb_repo is not None:
        knowledge_base = kb_repo.get(knowledge_base_id)
        if knowledge_base is None:
            raise HTTPException(status_code=404, detail=f"knowledge_base_not_found: {knowledge_base_id}")
        if knowledge_base.status != "active":
            request.app.state.orchestrator_cache.pop(knowledge_base_id, None)
            raise HTTPException(status_code=400, detail=f"knowledge_base_not_active: {knowledge_base_id}")

    cache: dict[str, LangGraphOrchestrator] = request.app.state.orchestrator_cache
    if knowledge_base_id not in cache:
        cache[knowledge_base_id] = build_orchestrator_for_kb(knowledge_base_id)
    return cache[knowledge_base_id]


def get_kb_repo(request: Request):
    from infra.bootstrap import _get_kb_repo
    from infra.settings import Settings

    settings = getattr(request.app.state, "settings", None) or Settings()
    return _get_kb_repo(settings)
