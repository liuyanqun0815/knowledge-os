from __future__ import annotations

from fastapi.testclient import TestClient

from akos.interfaces.api.main import create_app
from akos.application.ingest.domain_llm_extractor import DomainLlmExtractor
from akos.domain.ports.compiler import ExtractedClaim
from akos.bootstrap import DEFAULT_IN_MEMORY_KB_ID
from infra.settings import Settings, get_settings


def _disable_post_ingest(monkeypatch) -> None:
    monkeypatch.setenv("AKOS_USE_PG", "false")
    monkeypatch.setenv("AKOS_LLM_API_KEY", "test-key")
    monkeypatch.setenv("AKOS_CHUNK_LLM", "false")
    monkeypatch.setenv("AKOS_WIKI_COMPILE", "false")
    monkeypatch.setenv("AKOS_TOPIC_CLUSTER", "false")
    monkeypatch.setenv("AKOS_GRAPH_BACKEND", "memory")
    get_settings.cache_clear()


def test_upload_runs_hybrid_compile_and_finishes_succeeded(tmp_path, monkeypatch) -> None:
    from akos.interfaces.api.admin_api.upload_jobs import process_uploaded_source

    _disable_post_ingest(monkeypatch)
    app = create_app(data_root=str(tmp_path))
    settings = Settings(
        data_root=str(tmp_path),
        llm_api_key="test-key",
        chunk_llm=False,
        topic_cluster=False,
        wiki_compile=False,
    )
    app.state.settings = settings
    scheduled: list[tuple[object, tuple, dict]] = []
    sync_llm_calls: list[str] = []
    status_trace: list[str] = []

    def capture_task(self, func, *args, **kwargs) -> None:
        scheduled.append((func, args, kwargs))

    def track_sync_llm(
        self,
        text: str,
        *,
        document_anchor=None,
        section_title=None,
        section_summary=None,
        **_kwargs,
    ) -> list[ExtractedClaim]:
        sync_llm_calls.append(text)
        return []

    monkeypatch.setattr("starlette.background.BackgroundTasks.add_task", capture_task)
    monkeypatch.setattr(DomainLlmExtractor, "extract", track_sync_llm)

    response = TestClient(app).post(
        f"/admin/knowledge-bases/{DEFAULT_IN_MEMORY_KB_ID}/sources/upload",
        files={"file": ("policy.md", b"seven-day returns are supported", "text/markdown")},
        data={"source_type": "policy"},
    )

    assert response.status_code == 202, response.text
    assert response.json()["accepted_async"] is True
    source_id = response.json()["results"][0]["source_id"]
    assert len(scheduled) == 1
    task, args, kwargs = scheduled[0]
    assert task is process_uploaded_source
    assert not args
    assert kwargs["kb_id"] == DEFAULT_IN_MEMORY_KB_ID

    knowledge = kwargs["deps"].knowledge
    original_update = knowledge.update_source_status

    def trace_status(sid: str, status: str) -> None:
        if sid == source_id:
            status_trace.append(status)
        original_update(sid, status)

    monkeypatch.setattr(knowledge, "update_source_status", trace_status)
    kwargs["settings"] = settings
    task(**kwargs)

    assert sync_llm_calls, "background job should invoke LLM during compile"
    assert knowledge.get_source(source_id).status == "succeeded"
    assert "chunking" in status_trace
    assert "extracting_claims" in status_trace
    assert status_trace[-1] == "succeeded"
    assert "enriching" not in status_trace


def test_upload_marks_compiling_wiki_before_succeeded(tmp_path, monkeypatch) -> None:
    from akos.interfaces.api.admin_api.upload_jobs import process_uploaded_source
    import akos.application.ingest.chunk_enrichment as chunk_enrichment

    monkeypatch.setenv("AKOS_USE_PG", "false")
    monkeypatch.setenv("AKOS_LLM_API_KEY", "test-key")
    monkeypatch.setenv("AKOS_CHUNK_LLM", "false")
    monkeypatch.setenv("AKOS_TOPIC_CLUSTER", "false")
    monkeypatch.setenv("AKOS_WIKI_COMPILE", "true")
    monkeypatch.setenv("AKOS_GRAPH_BACKEND", "memory")
    get_settings.cache_clear()

    settings = Settings(
        data_root=str(tmp_path),
        llm_api_key="test-key",
        chunk_llm=False,
        topic_cluster=False,
        wiki_compile=True,
    )
    app = create_app(data_root=str(tmp_path))
    app.state.settings = settings
    scheduled: list[dict] = []
    wiki_calls: list[str] = []
    status_trace: list[str] = []

    def capture_task(self, func, *args, **kwargs) -> None:
        assert not args
        scheduled.append(kwargs)

    def fake_wiki(*, kb_id: str, source_id: str, deps, settings) -> None:
        wiki_calls.append(source_id)

    monkeypatch.setattr("starlette.background.BackgroundTasks.add_task", capture_task)
    monkeypatch.setattr(DomainLlmExtractor, "extract", lambda *a, **k: [])
    monkeypatch.setattr(chunk_enrichment, "compile_wiki_for_source", fake_wiki)

    response = TestClient(app).post(
        f"/admin/knowledge-bases/{DEFAULT_IN_MEMORY_KB_ID}/sources/upload",
        files={
            "file": (
                "policy.md",
                "七天无理由适用类目为非定制商品。".encode("utf-8"),
                "text/markdown",
            )
        },
    )
    assert response.status_code == 202, response.text
    source_id = response.json()["results"][0]["source_id"]
    kwargs = scheduled[0]
    assert kwargs["settings"].wiki_compile is True
    knowledge = kwargs["deps"].knowledge
    original_update = knowledge.update_source_status

    def trace_status(sid: str, status: str) -> None:
        if sid == source_id:
            status_trace.append(status)
        original_update(sid, status)

    monkeypatch.setattr(knowledge, "update_source_status", trace_status)
    process_uploaded_source(**kwargs)

    assert "compiling_wiki" in status_trace, status_trace
    assert status_trace.index("compiling_wiki") < status_trace.index("succeeded")
    assert wiki_calls == [source_id]
    assert knowledge.get_source(source_id).status == "succeeded"


def test_lifespan_marks_interrupted_enriching_as_failed(tmp_path, monkeypatch) -> None:
    from datetime import datetime, timezone
    from types import SimpleNamespace

    from akos.adapters.persistence.knowledge_memory import InMemoryKnowledge
    from akos.domain.models.knowledge import Source

    monkeypatch.setenv("AKOS_USE_PG", "false")
    monkeypatch.setenv("AKOS_CHUNK_LLM", "false")
    get_settings.cache_clear()
    app = create_app(data_root=str(tmp_path))
    knowledge = InMemoryKnowledge()
    knowledge.save_source(
        Source(
            id="stuck",
            title="stuck.md",
            type="policy",
            uri="file://stuck.md",
            version="1",
            created_at=datetime.now(timezone.utc),
            status="enriching",
        )
    )
    deps = SimpleNamespace(knowledge=knowledge)
    app.state.orchestrator_cache["kb-resume"] = SimpleNamespace(deps=deps)

    with TestClient(app):
        pass

    assert knowledge.get_source("stuck").status == "failed"
