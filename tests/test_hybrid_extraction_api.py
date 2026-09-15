from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import create_app
from compiler.domain_llm_extractor import DomainLlmExtractor
from compiler.ports import ExtractedClaim
from infra.bootstrap import DEFAULT_IN_MEMORY_KB_ID
from infra.settings import Settings
from knowledge.memory_repo import InMemoryKnowledge
from knowledge.models import Source


def test_upload_runs_hybrid_compile_and_schedules_enrichment(tmp_path, monkeypatch) -> None:
    from admin_api.upload_jobs import process_uploaded_source

    monkeypatch.setenv("AKOS_USE_PG", "false")
    monkeypatch.setenv("AKOS_LLM_API_KEY", "test-key")
    monkeypatch.setenv("AKOS_EXTRACT_LLM", "true")
    app = create_app(data_root=str(tmp_path))
    app.state.settings = Settings(data_root=str(tmp_path), extract_llm=True, llm_api_key="test-key")
    scheduled: list[tuple[object, tuple, dict]] = []
    sync_llm_calls: list[str] = []

    def capture_task(self, func, *args, **kwargs) -> None:
        scheduled.append((func, args, kwargs))

    def track_sync_llm(self, text: str) -> list[ExtractedClaim]:
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
    assert kwargs["source_type"] == "policy"

    task(**kwargs)
    assert sync_llm_calls, "background job should invoke LLM when extract_llm is enabled"
    assert kwargs["deps"].knowledge.get_source(source_id).status == "succeeded"


def test_enrich_open_predicates_writes_novel_claim(tmp_path, monkeypatch) -> None:
    from admin_api.upload_jobs import process_uploaded_source
    from compiler.enrichment import enrich_source

    monkeypatch.setenv("AKOS_USE_PG", "false")
    monkeypatch.setenv("AKOS_LLM_API_KEY", "test-key")
    monkeypatch.setenv("AKOS_EXTRACT_OPEN_PREDICATES", "true")
    app = create_app(data_root=str(tmp_path))
    open_settings = Settings(
        data_root=str(tmp_path),
        extract_rules=False,
        extract_llm=True,
        llm_api_key="test-key",
        extract_open_predicates=True,
    )
    app.state.settings = open_settings
    scheduled: list[tuple[object, dict]] = []

    def capture_task(self, func, *args, **kwargs) -> None:
        assert not args
        scheduled.append((func, kwargs))

    monkeypatch.setattr("starlette.background.BackgroundTasks.add_task", capture_task)
    monkeypatch.setattr(DomainLlmExtractor, "extract", lambda self, text: [])
    source_text = "七天无理由由买家承担"
    response = TestClient(app).post(
        f"/admin/knowledge-bases/{DEFAULT_IN_MEMORY_KB_ID}/sources/upload",
        files={"file": ("policy.md", source_text.encode(), "text/markdown")},
    )
    assert response.status_code == 202, response.text
    source_id = response.json()["results"][0]["source_id"]

    task, kwargs = scheduled[0]
    assert task is process_uploaded_source
    kwargs["settings"] = open_settings
    task(**kwargs)
    assert kwargs["deps"].knowledge.get_source_text(source_id) == source_text

    extracted_texts: list[str] = []

    def extract_unknown(self, text: str) -> list[ExtractedClaim]:
        extracted_texts.append(text)
        return [
            ExtractedClaim(
                subject="七天无理由",
                predicate="unknown_predicate",
                object="买家",
                confidence=0.9,
                quote=text,
                start=0,
                end=len(text),
            )
        ]

    monkeypatch.setattr(DomainLlmExtractor, "extract", extract_unknown)
    enrich_source(
        kb_id=DEFAULT_IN_MEMORY_KB_ID,
        source_id=source_id,
        deps=kwargs["deps"],
        settings=open_settings,
    )

    knowledge = kwargs["deps"].knowledge
    assert extracted_texts == [source_text]
    assert knowledge.get_source(source_id).status == "succeeded"
    active = [c for c in knowledge.get_claims_by_status("active") if c.predicate == "unknown_predicate"]
    assert active
    assert not any(q["reason"] == "invalid_predicate" for q in knowledge.list_quarantine())


def test_enrich_closed_predicates_quarantines_novel_claim(tmp_path, monkeypatch) -> None:
    from admin_api.upload_jobs import process_uploaded_source
    from compiler.enrichment import enrich_source

    monkeypatch.setenv("AKOS_USE_PG", "false")
    monkeypatch.setenv("AKOS_LLM_API_KEY", "test-key")
    monkeypatch.setenv("AKOS_EXTRACT_OPEN_PREDICATES", "false")
    app = create_app(data_root=str(tmp_path))
    closed_settings = Settings(
        data_root=str(tmp_path),
        extract_rules=False,
        extract_llm=True,
        llm_api_key="test-key",
        extract_open_predicates=False,
    )
    app.state.settings = closed_settings
    scheduled: list[tuple[object, dict]] = []

    def capture_task(self, func, *args, **kwargs) -> None:
        assert not args
        scheduled.append((func, kwargs))

    monkeypatch.setattr("starlette.background.BackgroundTasks.add_task", capture_task)
    monkeypatch.setattr(DomainLlmExtractor, "extract", lambda self, text: [])
    source_text = "七天无理由由买家承担"
    response = TestClient(app).post(
        f"/admin/knowledge-bases/{DEFAULT_IN_MEMORY_KB_ID}/sources/upload",
        files={"file": ("policy.md", source_text.encode(), "text/markdown")},
    )
    assert response.status_code == 202, response.text
    source_id = response.json()["results"][0]["source_id"]

    task, kwargs = scheduled[0]
    assert task is process_uploaded_source
    kwargs["settings"] = closed_settings
    task(**kwargs)

    def extract_unknown(self, text: str) -> list[ExtractedClaim]:
        return [
            ExtractedClaim(
                subject="七天无理由",
                predicate="unknown_predicate",
                object="买家",
                confidence=0.9,
                quote=text,
                start=0,
                end=len(text),
            )
        ]

    monkeypatch.setattr(DomainLlmExtractor, "extract", extract_unknown)
    enrich_source(
        kb_id=DEFAULT_IN_MEMORY_KB_ID,
        source_id=source_id,
        deps=kwargs["deps"],
        settings=closed_settings,
    )
    assert kwargs["deps"].knowledge.list_quarantine()[-1]["reason"] == "invalid_predicate"


def test_lifespan_retries_only_enriching_sources(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AKOS_USE_PG", "false")
    app = create_app(data_root=str(tmp_path))
    knowledge = InMemoryKnowledge()
    for source_id, status in (("resume-me", "enriching"), ("leave-me", "ready")):
        knowledge.save_source(
            Source(
                id=source_id,
                title=f"{source_id}.md",
                type="policy",
                uri=f"file://{source_id}.md",
                version="1",
                created_at=datetime.now(timezone.utc),
                status=status,
            )
        )
    deps = SimpleNamespace(knowledge=knowledge)
    app.state.orchestrator_cache["kb-resume"] = SimpleNamespace(deps=deps)
    resumed: list[tuple[str, str]] = []

    def record_resume(*, kb_id: str, source_id: str, deps, settings: Settings) -> None:
        resumed.append((kb_id, source_id))

    monkeypatch.setattr("app.main.enrich_source", record_resume)

    with TestClient(app):
        pass

    assert resumed == [("kb-resume", "resume-me")]
