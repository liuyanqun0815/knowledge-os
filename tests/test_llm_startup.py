from __future__ import annotations

import pytest

from akos.adapters.llm.client import LlmConfigError, ensure_llm_settings
from infra.settings import Settings


def test_ensure_llm_settings_raises_without_key() -> None:
    with pytest.raises(LlmConfigError, match="AKOS_LLM_API_KEY"):
        ensure_llm_settings(Settings(_env_file=None, llm_api_key=""))


def test_create_app_requires_llm(monkeypatch, tmp_path) -> None:
    from akos.interfaces.api.main import create_app

    def _settings_without_key(**kwargs: object) -> Settings:
        data_root = kwargs.get("data_root", str(tmp_path))
        return Settings(_env_file=None, llm_api_key="", data_root=str(data_root))

    monkeypatch.setattr("akos.interfaces.api.main.Settings", _settings_without_key)
    with pytest.raises(LlmConfigError, match="启动失败"):
        create_app(data_root=str(tmp_path))


def test_create_app_ok_with_key(tmp_path) -> None:
    from akos.interfaces.api.main import create_app

    app = create_app(data_root=str(tmp_path), validate_llm=True)
    assert app.title == "AKOS"
