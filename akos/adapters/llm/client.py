from __future__ import annotations

import logging
import time

import httpx
from langsmith import traceable

from infra.settings import Settings, get_settings

logger = logging.getLogger(__name__)

_RETRYABLE_EXCEPTIONS = (
    httpx.ConnectError,
    httpx.ConnectTimeout,
    httpx.ReadTimeout,
    httpx.WriteTimeout,
    httpx.PoolTimeout,
    httpx.RemoteProtocolError,
    httpx.NetworkError,
)


class LlmConfigError(RuntimeError):
    """Raised when LLM is invoked without required configuration."""


class OpenAiCompatibleClient:
    """Minimal OpenAI-compatible chat completions client."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    @property
    def is_configured(self) -> bool:
        return bool(self._settings.llm_api_key)

    @traceable(
        name="akos.llm.chat_completions",
        run_type="llm",
        metadata={"ls_provider": "openai-compatible"},
    )
    def chat_completions(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.0,
        timeout: float = 60.0,
        max_retries: int = 3,
    ) -> str:
        api_key = self._settings.llm_api_key
        if not api_key:
            raise LlmConfigError(
                "AKOS_LLM_API_KEY is not set. "
                "Configure AKOS_LLM_BASE_URL, AKOS_LLM_API_KEY, and AKOS_LLM_MODEL in .env."
            )

        model = self._settings.llm_model
        try:
            from langsmith.run_helpers import get_current_run_tree

            run_tree = get_current_run_tree()
            if run_tree is not None:
                run_tree.metadata["ls_model_name"] = model
        except ImportError:
            pass

        base_url = self._settings.llm_base_url.rstrip("/")
        url = f"{base_url}/chat/completions"
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        if not self._settings.llm_thinking:
            payload["thinking"] = {"type": "disabled"}
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        attempts = max(1, max_retries)
        data = None
        for attempt in range(1, attempts + 1):
            try:
                with httpx.Client(timeout=timeout) as client:
                    response = client.post(url, json=payload, headers=headers)
                    response.raise_for_status()
                    data = response.json()
                break
            except _RETRYABLE_EXCEPTIONS as exc:
                if attempt >= attempts:
                    raise
                delay = min(2 ** (attempt - 1), 8)
                logger.warning(
                    "LLM request failed (%s), retry %s/%s in %ss: %s",
                    type(exc).__name__,
                    attempt,
                    attempts,
                    delay,
                    exc,
                )
                time.sleep(delay)

        assert data is not None
        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError("LLM response missing choices")
        message = choices[0].get("message") or {}
        content = message.get("content")
        if not isinstance(content, str):
            raise RuntimeError("LLM response missing message content")
        return content
