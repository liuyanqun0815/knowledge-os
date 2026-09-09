from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import create_app
from compiler.domain_llm_extractor import DomainLlmExtractor
from compiler.enrichment import enrich_source
from compiler.ports import ExtractedClaim
from infra.bootstrap import DEFAULT_IN_MEMORY_KB_ID
from infra.settings import Settings
from knowledge.memory_repo import InMemoryKnowledge
from knowledge.models import Source


def test_upload_schedules_enrichment_without_calling_llm_synchronously(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AKOS_USE_PG", "false")
    monkeypatch.setenv("AKOS_LLM_API_KEY", "test-key")
    monkeypatch.setenv("AKOS_EXTRACT_LLM", "true")
    app = create_app(data_root=str(tmp_path))
    app.state.settings = Settings(data_root=str(tmp_path), extract_llm=True, llm_api_key="test-key")
    scheduled: list[tuple[object, tuple, dict]] = []

    def capture_task(self, func, *args, **kwargs) -> None:
        scheduled.append((func, args, kwargs))

    def reject_synchronous_llm(self, text: str) -> list[ExtractedClaim]:
        raise AssertionError("the synchronous upload path must not call the LLM")

    monkeypatch.setattr("starlette.background.BackgroundTasks.add_task", capture_task)
    monkeypatch.setattr(DomainLlmExtractor, "extract", reject_synchronous_llm)

    response = TestClient(app).post(
        f"/admin/knowledge-bases/{DEFAULT_IN_MEMORY_KB_ID}/sources/upload",
        files={"file": ("policy.md", b"seven-day returns are supported", "text/markdown")},
        data={"source_type": "policy"},
    )

    assert response.status_code == 200, response.text
    source_id = response.json()["results"][0]["source_id"]
    assert len(scheduled) == 1
    task, args, kwargs = scheduled[0]
    assert task is enrich_source
    assert not args
    assert kwargs["kb_id"] == DEFAULT_IN_MEMORY_KB_ID
    assert kwargs["source_id"] == source_id
    assert kwargs["deps"].knowledge.get_source(source_id).status == "enriching"


def test_scheduled_enrichment_quarantines_unknown_predicate(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AKOS_USE_PG", "false")
    monkeypatch.setenv("AKOS_LLM_API_KEY", "test-key")
    app = create_app(data_root=str(tmp_path))
    app.state.settings = Settings(data_root=str(tmp_path), extract_llm=True, llm_api_key="test-key")
    scheduled: list[tuple[object, dict]] = []

    def capture_task(self, func, *args, **kwargs) -> None:
        assert not args
        scheduled.append((func, kwargs))

    monkeypatch.setattr("starlette.background.BackgroundTasks.add_task", capture_task)
    source_text = "七天无理由由买家承担"
    response = TestClient(app).post(
        f"/admin/knowledge-bases/{DEFAULT_IN_MEMORY_KB_ID}/sources/upload",
        files={"file": ("policy.md", source_text.encode(), "text/markdown")},
    )
    assert response.status_code == 200, response.text

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
    task, kwargs = scheduled[0]
    assert kwargs["settings"].extract_llm is True
    assert kwargs["deps"].llm_client.is_configured is True
    assert kwargs["deps"].knowledge.get_source_text(kwargs["source_id"]) == source_text
    task(**kwargs)

    knowledge = kwargs["deps"].knowledge
    assert extracted_texts == [source_text]
    assert knowledge.get_source(kwargs["source_id"]).status == "succeeded"
    assert knowledge.list_quarantine()[-1]["reason"] == "invalid_predicate"


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
