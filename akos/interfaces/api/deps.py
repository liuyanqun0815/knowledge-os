from fastapi import HTTPException, Request

from infra.bootstrap import _build_repos, build_orchestrator_for_kb
from infra.settings import Settings
from akos.domain.ports.knowledge import KnowledgePort
from akos.application.ask.service import LangGraphOrchestrator


def _ensure_active_kb(knowledge_base_id: str, request: Request) -> None:
    kb_repo = get_kb_repo(request)
    if kb_repo is None:
        return
    knowledge_base = kb_repo.get(knowledge_base_id)
    if knowledge_base is None:
        raise HTTPException(status_code=404, detail=f"knowledge_base_not_found: {knowledge_base_id}")
    if knowledge_base.status != "active":
        request.app.state.orchestrator_cache.pop(knowledge_base_id, None)
        raise HTTPException(status_code=400, detail=f"knowledge_base_not_active: {knowledge_base_id}")


def build_orchestrator_for_request(knowledge_base_id: str, request: Request) -> LangGraphOrchestrator:
    _ensure_active_kb(knowledge_base_id, request)
    cache: dict[str, LangGraphOrchestrator] = request.app.state.orchestrator_cache
    if knowledge_base_id not in cache:
        settings = getattr(request.app.state, "settings", None) or Settings()
        cache[knowledge_base_id] = build_orchestrator_for_kb(knowledge_base_id, settings=settings)
    return cache[knowledge_base_id]


def get_knowledge_for_request(knowledge_base_id: str, request: Request) -> KnowledgePort:
    """Return KnowledgePort without loading embedding/rerank when possible.

    Prefer an already-warmed orchestrator cache. On Postgres, open a fresh
    PgKnowledge handle so browse/list APIs stay light. In-memory mode falls back
    to the full orchestrator so the shared store stays consistent.
    """
    _ensure_active_kb(knowledge_base_id, request)
    cache: dict[str, LangGraphOrchestrator] = request.app.state.orchestrator_cache
    cached = cache.get(knowledge_base_id)
    if cached is not None:
        return cached.deps.knowledge

    settings = getattr(request.app.state, "settings", None) or Settings()
    if settings.use_pg:
        knowledge, _, _, _ = _build_repos(knowledge_base_id, settings)
        return knowledge
    return build_orchestrator_for_request(knowledge_base_id, request).deps.knowledge


def get_kb_repo(request: Request):
    settings = getattr(request.app.state, "settings", None) or Settings()
    from infra.bootstrap import _get_kb_repo

    return _get_kb_repo(settings)
