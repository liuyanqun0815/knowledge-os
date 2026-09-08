from __future__ import annotations

import httpx

from infra.settings import Settings, get_settings


class LlmConfigError(RuntimeError):
    """Raised when LLM is invoked without required configuration."""


class OpenAiCompatibleClient:
    """Minimal OpenAI-compatible chat completions client."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    @property
    def is_configured(self) -> bool:
        return bool(self._settings.llm_api_key)

    def chat_completions(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.0,
        timeout: float = 60.0,
    ) -> str:
        api_key = self._settings.llm_api_key
        if not api_key:
            raise LlmConfigError(
                "AKOS_LLM_API_KEY is not set. "
                "Configure AKOS_LLM_BASE_URL, AKOS_LLM_API_KEY, and AKOS_LLM_MODEL in .env."
            )

        base_url = self._settings.llm_base_url.rstrip("/")
        url = f"{base_url}/chat/completions"
        payload = {
            "model": self._settings.llm_model,
            "messages": messages,
            "temperature": temperature,
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        with httpx.Client(timeout=timeout) as client:
            response = client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError("LLM response missing choices")
        message = choices[0].get("message") or {}
        content = message.get("content")
        if not isinstance(content, str):
            raise RuntimeError("LLM response missing message content")
        return content
