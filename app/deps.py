from fastapi import Request

from infra.bootstrap import build_orchestrator_for_kb
from orchestrator.service import LangGraphOrchestrator


def build_orchestrator_for_request(knowledge_base_id: str, request: Request) -> LangGraphOrchestrator:
    cache: dict[str, LangGraphOrchestrator] = request.app.state.orchestrator_cache
    if knowledge_base_id not in cache:
        cache[knowledge_base_id] = build_orchestrator_for_kb(knowledge_base_id)
    return cache[knowledge_base_id]


def get_kb_repo(request: Request):
    from infra.bootstrap import _get_kb_repo
    from infra.settings import Settings

    settings = getattr(request.app.state, "settings", None) or Settings()
    return _get_kb_repo(settings)
