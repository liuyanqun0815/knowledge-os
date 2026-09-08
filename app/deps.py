from fastapi import Request

from orchestrator.service import LangGraphOrchestrator


def get_orchestrator(request: Request) -> LangGraphOrchestrator:
    return request.app.state.orchestrator
