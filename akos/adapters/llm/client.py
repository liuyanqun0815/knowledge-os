from __future__ import annotations

import logging
import time
from typing import Any

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
    """未配置 LLM 仍发起调用时抛出。"""


class LlmCallError(RuntimeError):
    """LLM 已配置但调用失败（网络、HTTP、响应格式等）。"""


_LLM_ENV_HINT = "请在 .env 配置 AKOS_LLM_BASE_URL、AKOS_LLM_API_KEY、AKOS_LLM_MODEL。"


def ensure_llm_settings(settings: Settings | None = None) -> None:
    """进程启动时校验 LLM 必填项；未配置则抛 ``LlmConfigError``。"""
    resolved = settings or get_settings()
    if not str(resolved.llm_api_key or "").strip():
        raise LlmConfigError(f"服务启动失败：未配置 AKOS_LLM_API_KEY。{_LLM_ENV_HINT}")
    if not str(resolved.llm_base_url or "").strip():
        raise LlmConfigError(f"服务启动失败：未配置 AKOS_LLM_BASE_URL。{_LLM_ENV_HINT}")
    if not str(resolved.llm_model or "").strip():
        raise LlmConfigError(f"服务启动失败：未配置 AKOS_LLM_MODEL。{_LLM_ENV_HINT}")


def require_llm_configured(client: Any | None, *, feature: str) -> None:
    """在需要 LLM 的功能入口校验 client；未配置时抛出 ``LlmConfigError``。"""
    if client is not None and getattr(client, "is_configured", False):
        return
    raise LlmConfigError(f"{feature} 需要 LLM，但未配置 AKOS_LLM_API_KEY。{_LLM_ENV_HINT}")


class OpenAiCompatibleClient:
    """OpenAI 兼容的最小 chat completions 客户端。"""

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
            raise LlmConfigError(f"未配置 AKOS_LLM_API_KEY。{_LLM_ENV_HINT}")

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
        last_retryable: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                with httpx.Client(timeout=timeout) as client:
                    response = client.post(url, json=payload, headers=headers)
                    response.raise_for_status()
                    data = response.json()
                break
            except _RETRYABLE_EXCEPTIONS as exc:
                last_retryable = exc
                if attempt >= attempts:
                    raise LlmCallError(
                        f"LLM 请求失败（{type(exc).__name__}，已重试 {attempts} 次）: {exc}"
                    ) from exc
                delay = min(2 ** (attempt - 1), 8)
                logger.warning(
                    "LLM 请求失败 (%s)，重试 %s/%s，%ss 后: %s",
                    type(exc).__name__,
                    attempt,
                    attempts,
                    delay,
                    exc,
                )
                time.sleep(delay)
            except httpx.HTTPStatusError as exc:
                body = (exc.response.text or "")[:200]
                raise LlmCallError(
                    f"LLM HTTP {exc.response.status_code}: {body or exc.response.reason_phrase}"
                ) from exc

        if data is None:
            raise LlmCallError(
                f"LLM 请求未返回有效响应: {last_retryable}" if last_retryable else "LLM 请求未返回有效响应"
            )
        choices = data.get("choices") or []
        if not choices:
            raise LlmCallError("LLM 响应缺少 choices")
        message = choices[0].get("message") or {}
        content = message.get("content")
        if not isinstance(content, str):
            raise LlmCallError("LLM 响应缺少 message.content")
        return content
