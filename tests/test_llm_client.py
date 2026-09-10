from unittest.mock import MagicMock, patch

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

    with patch("infra.llm.httpx.Client") as mock_client_cls:
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

    with patch("infra.llm.httpx.Client") as mock_client_cls:
        mock_client_cls.return_value.__enter__.return_value.post.return_value = mock_response
        client.chat_completions([{"role": "user", "content": "hi"}])

    payload = mock_client_cls.return_value.__enter__.return_value.post.call_args.kwargs["json"]
    assert "thinking" not in payload
