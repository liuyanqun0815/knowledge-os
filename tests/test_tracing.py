from infra.settings import Settings
from infra.tracing import build_run_config, configure_langsmith


def test_llm_model_strips_whitespace():
    settings = Settings(llm_model="\tdeepseek-v4-flash\n")
    assert settings.llm_model == "deepseek-v4-flash"


def test_configure_langsmith_from_langchain_env_fields(monkeypatch):
    monkeypatch.delenv("LANGCHAIN_TRACING_V2", raising=False)
    monkeypatch.delenv("LANGCHAIN_API_KEY", raising=False)
    settings = Settings(
        langchain_tracing_v2=True,
        langchain_api_key="langchain-key",
        langchain_project="akos-from-env",
    )
    assert configure_langsmith(settings) is True
    import os

    assert os.environ["LANGCHAIN_TRACING_V2"] == "true"
    assert os.environ["LANGCHAIN_API_KEY"] == "langchain-key"
    assert os.environ["LANGCHAIN_PROJECT"] == "akos-from-env"


def test_build_run_config_attaches_tracer_callback(monkeypatch):
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")
    monkeypatch.setenv("LANGCHAIN_API_KEY", "test-key")
    monkeypatch.setenv("LANGCHAIN_PROJECT", "akos-test")

    config = build_run_config(run_name="akos.ingest", tags=["ingest"])
    assert config["run_name"] == "akos.ingest"
    assert config.get("callbacks")


def test_configure_langsmith_from_akos_settings(monkeypatch):
    monkeypatch.delenv("LANGCHAIN_TRACING_V2", raising=False)
    monkeypatch.delenv("LANGCHAIN_API_KEY", raising=False)
    settings = Settings(
        langsmith_tracing=True,
        langsmith_api_key="test-key",
        langsmith_project="akos-test",
    )
    assert configure_langsmith(settings) is True
    import os

    assert os.environ["LANGCHAIN_TRACING_V2"] == "true"
    assert os.environ["LANGCHAIN_API_KEY"] == "test-key"
    assert os.environ["LANGCHAIN_PROJECT"] == "akos-test"
