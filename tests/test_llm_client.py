from unittest.mock import MagicMock, patch

import httpx
import pytest

from infra.llm import OpenAiCompatibleClient
from infra.settings import Settings


def test_chat_completions_disables_deepseek_thinking_by_default():
    settings = Settings(llm_api_key="test-key", llm_thinking=False)
    client = OpenAiCompatibleClient(settings)
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "choices": [{"message": {"content": '{"answer":"ok","citations":[]}'}}]
    }

    with patch("akos.adapters.llm.client.httpx.Client") as mock_client_cls:
        mock_client_cls.return_value.__enter__.return_value.post.return_value = mock_response
        client.chat_completions([{"role": "user", "content": "hi"}])

    payload = mock_client_cls.return_value.__enter__.return_value.post.call_args.kwargs["json"]
    assert payload["thinking"] == {"type": "disabled"}


def test_chat_completions_omits_thinking_flag_when_enabled():
    settings = Settings(llm_api_key="test-key", llm_thinking=True)
    client = OpenAiCompatibleClient(settings)
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"choices": [{"message": {"content": "ok"}}]}

    with patch("akos.adapters.llm.client.httpx.Client") as mock_client_cls:
        mock_client_cls.return_value.__enter__.return_value.post.return_value = mock_response
        client.chat_completions([{"role": "user", "content": "hi"}])

    payload = mock_client_cls.return_value.__enter__.return_value.post.call_args.kwargs["json"]
    assert "thinking" not in payload


def test_chat_completions_retries_transient_connect_error():
    settings = Settings(llm_api_key="test-key", llm_thinking=False)
    client = OpenAiCompatibleClient(settings)
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"choices": [{"message": {"content": "ok"}}]}

    with (
        patch("akos.adapters.llm.client.httpx.Client") as mock_client_cls,
        patch("akos.adapters.llm.client.time.sleep") as sleep,
    ):
        post = mock_client_cls.return_value.__enter__.return_value.post
        post.side_effect = [
            httpx.ConnectError("SSL EOF"),
            httpx.ConnectError("SSL EOF"),
            mock_response,
        ]
        content = client.chat_completions([{"role": "user", "content": "hi"}], max_retries=3)

    assert content == "ok"
    assert post.call_count == 3
    assert sleep.call_count == 2


def test_chat_completions_raises_after_retries_exhausted():
    settings = Settings(llm_api_key="test-key", llm_thinking=False)
    client = OpenAiCompatibleClient(settings)

    with (
        patch("akos.adapters.llm.client.httpx.Client") as mock_client_cls,
        patch("akos.adapters.llm.client.time.sleep"),
    ):
        post = mock_client_cls.return_value.__enter__.return_value.post
        post.side_effect = httpx.ConnectError("SSL EOF")
        with pytest.raises(httpx.ConnectError):
            client.chat_completions([{"role": "user", "content": "hi"}], max_retries=2)

    assert post.call_count == 2
