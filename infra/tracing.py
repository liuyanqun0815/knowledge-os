from __future__ import annotations

import os
from typing import Any

from infra.settings import Settings, get_settings


def is_tracing_enabled() -> bool:
    return os.getenv("LANGCHAIN_TRACING_V2", "").lower() in {"1", "true", "yes"}


def configure_langsmith(settings: Settings | None = None) -> bool:
    """Enable LangSmith tracing; sync LANGCHAIN_* into os.environ for LangGraph/langsmith."""
    settings = settings or get_settings()

    tracing_enabled = settings.langchain_tracing_v2 or settings.langsmith_tracing
    if not tracing_enabled:
        tracing_enabled = os.getenv("LANGCHAIN_TRACING_V2", "").lower() in {"1", "true", "yes"}
    if not tracing_enabled:
        return False

    api_key = (
        settings.langchain_api_key
        or settings.langsmith_api_key
        or os.getenv("LANGCHAIN_API_KEY")
        or os.getenv("LANGSMITH_API_KEY")
        or ""
    )
    if not api_key:
        return False

    project = settings.langchain_project or settings.langsmith_project or os.getenv("LANGCHAIN_PROJECT") or "akos"
    endpoint = settings.langchain_endpoint or settings.langsmith_endpoint or os.getenv("LANGCHAIN_ENDPOINT")

    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_API_KEY"] = api_key
    os.environ["LANGCHAIN_PROJECT"] = project
    if endpoint:
        os.environ["LANGCHAIN_ENDPOINT"] = endpoint
    return True


def build_run_config(
    *,
    run_name: str,
    metadata: dict[str, Any] | None = None,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    """Build LangGraph invoke config for LangSmith run grouping."""
    config: dict[str, Any] = {"run_name": run_name}
    if metadata:
        config["metadata"] = metadata
    if tags:
        config["tags"] = tags

    if is_tracing_enabled():
        try:
            from langchain_core.tracers.langchain import LangChainTracer

            project = os.getenv("LANGCHAIN_PROJECT", "akos")
            config["callbacks"] = [LangChainTracer(project_name=project)]
        except ImportError:
            pass
    return config
