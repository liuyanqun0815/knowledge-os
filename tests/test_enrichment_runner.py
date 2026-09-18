from __future__ import annotations

import json
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from akos.application.ingest.enrichment import enrich_source
from akos.application.ingest.extraction_spec import LlmExtractionSpec
from akos.domain.ports.compiler import ExtractedClaim
from akos.application.ingest.service import KnowledgeCompiler
from akos.adapters.persistence.evidence_memory import InMemoryEvidence
from akos.adapters.persistence.graph_memory import InMemoryGraph
from infra.settings import Settings
from akos.adapters.persistence.knowledge_memory import InMemoryKnowledge
from knowledge.models import Source
from ontology.registry import InMemoryOntology


class _UnusedExtractor:
    def extract(self, text: str) -> list[ExtractedClaim]:
        raise AssertionError("enrichment must use DomainLlmExtractor")


class _Domain:
    def llm_extraction_spec(self) -> LlmExtractionSpec:
        return LlmExtractionSpec(allowed_predicates=["倡导"], entity_types=["Concept"])


class MockLlmClient:
    def __init__(self, responses: list[object], *, is_configured: bool = True) -> None:
        self.is_configured = is_configured
        self._responses = iter(responses)
        self.calls = 0

    def chat_completions(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.0,
        timeout: float = 60.0,
    ) -> str:
        self.calls += 1
        response = next(self._responses)
        if isinstance(response, Exception):
            raise response
        return json.dumps(response, ensure_ascii=False)


def _claim(
    quote: str,
    *,
    obj: str = "诚信经营",
    confidence: float = 0.9,
) -> dict[str, object]:
    return {
        "subject": "公司",
        "predicate": "倡导",
        "object": obj,
        "confidence": confidence,
        "quote": quote,
    }


def _deps(text: str | None, client: MockLlmClient) -> SimpleNamespace:
    knowledge = InMemoryKnowledge()
    knowledge.save_source(
        Source(
            id="source-1",
            title="culture.md",
            type="policy",
            uri="file://culture.md",
            version="1",
            created_at=datetime.now(timezone.utc),
            status="ready",
        )
    )
    if text is not None:
        knowledge.save_source_text("source-1", text)
    compiler = KnowledgeCompiler(
        InMemoryOntology(),
        knowledge,
        InMemoryGraph(),
        InMemoryEvidence(),
        _UnusedExtractor(),
    )
    return SimpleNamespace(
        knowledge=knowledge,
        compiler=compiler,
        domain=_Domain(),
        llm_client=client,
        chunk_retrieval=None,
        knowledge_base_id="kb-1",
    )


def _settings(**overrides: object) -> Settings:
    values = {
        "extract_llm": True,
        "chunk_max_chars": 3000,
        "chunk_max_per_doc": 40,
        "extract_min_confidence": 0.5,
    }
    values.update(overrides)
    return Settings(**values)


@pytest.mark.parametrize(
    ("extract_llm", "is_configured"),
    [(False, True), (True, False)],
)
def test_enrich_source_skips_when_llm_is_disabled_or_unconfigured(
    extract_llm: bool,
    is_configured: bool,
) -> None:
    client = MockLlmClient([], is_configured=is_configured)
    deps = _deps("公司倡导诚信经营。", client)

    enrich_source(
        kb_id="kb-1",
        source_id="source-1",
        deps=deps,
        settings=_settings(extract_llm=extract_llm),
    )

    assert deps.knowledge.get_source("source-1").status == "succeeded"
    assert client.calls == 0


def test_enrich_source_applies_mock_llm_claims_and_quarantines_low_confidence() -> None:
    text = "公司倡导诚信经营。公司倡导持续学习。"
    client = MockLlmClient(
        [
            [
                _claim("公司倡导诚信经营"),
                _claim("公司倡导持续学习", obj="持续学习", confidence=0.4),
            ]
        ]
    )
    deps = _deps(text, client)

    enrich_source(kb_id="kb-1", source_id="source-1", deps=deps, settings=_settings())

    assert deps.knowledge.get_source("source-1").status == "succeeded"
    assert len(deps.knowledge.get_claims_for_source("source-1")) == 1
    assert deps.knowledge.list_quarantine()[0]["reason"] == "low_confidence"


def test_enrich_source_retries_each_failed_chunk_once_and_marks_partial() -> None:
    client = MockLlmClient(
        [
            RuntimeError("temporary"),
            [_claim("alpha", obj="first")],
            RuntimeError("persistent"),
            RuntimeError("persistent"),
        ]
    )
    deps = _deps("alpha\n\nbeta", client)

    enrich_source(
        kb_id="kb-1",
        source_id="source-1",
        deps=deps,
        settings=_settings(chunk_max_chars=20),
    )

    assert client.calls == 4
    assert deps.knowledge.get_source("source-1").status == "succeeded_partial"
    assert len(deps.knowledge.get_claims_for_source("source-1")) == 1


def test_enrich_source_marks_truncated_documents_partial() -> None:
    client = MockLlmClient([[]])
    deps = _deps("alpha\n\nbeta", client)

    enrich_source(
        kb_id="kb-1",
        source_id="source-1",
        deps=deps,
        settings=_settings(chunk_max_per_doc=1),
    )

    assert deps.knowledge.get_source("source-1").status == "succeeded_partial"


def test_enrich_source_marks_fatal_errors_failed() -> None:
    deps = _deps(None, MockLlmClient([]))

    with pytest.raises(RuntimeError, match="source text not found"):
        enrich_source(kb_id="kb-1", source_id="source-1", deps=deps, settings=_settings())

    assert deps.knowledge.get_source("source-1").status == "failed"


def test_enrich_source_uses_source_chunk_title_as_subject_anchor(monkeypatch) -> None:
    from datetime import datetime, timezone

    from akos.application.ingest import enrichment
    from knowledge.models import SourceChunk

    calls: list[str | None] = []

    class FakeExtractor:
        def __init__(self, *args, **kwargs):
            pass

        def extract(self, text, *, document_anchor=None):
            calls.append(document_anchor)
            return []

    monkeypatch.setattr(enrichment, "DomainLlmExtractor", FakeExtractor)
    monkeypatch.setattr(enrichment, "resolve_document_anchor", lambda text, title=None: "文档级产品")

    text = "## 个人信用贷款\n\n无需抵押。\n\n## 房屋贷款\n\n有抵押。\n"
    client = MockLlmClient([])
    deps = _deps(text, client)
    now = datetime.now(timezone.utc)
    deps.knowledge.save_chunks(
        "source-1",
        [
            SourceChunk(
                id="c1",
                source_id="source-1",
                chunk_index=0,
                title="个人信用贷款",
                summary=None,
                text="## 个人信用贷款\n\n无需抵押。\n\n",
                start=0,
                end=20,
                section_path=["个人信用贷款"],
                topics=[],
                token_count=5,
                status="active",
                content_hash="h1",
                created_at=now,
            ),
            SourceChunk(
                id="c2",
                source_id="source-1",
                chunk_index=1,
                title="房屋贷款",
                summary=None,
                text="## 房屋贷款\n\n有抵押。\n",
                start=20,
                end=40,
                section_path=["房屋贷款"],
                topics=[],
                token_count=4,
                status="active",
                content_hash="h2",
                created_at=now,
            ),
        ],
    )

    enrich_source(kb_id="kb-1", source_id="source-1", deps=deps, settings=_settings())

    assert calls == ["个人信用贷款", "房屋贷款"]


def test_enrich_source_passes_document_anchor(monkeypatch) -> None:
    from akos.application.ingest import enrichment

    calls: list[str | None] = []

    class FakeExtractor:
        def __init__(self, *args, **kwargs):
            pass

        def extract(self, text, *, document_anchor=None):
            calls.append(document_anchor)
            return []

    monkeypatch.setattr(enrichment, "DomainLlmExtractor", FakeExtractor)
    monkeypatch.setattr(
        enrichment,
        "resolve_document_anchor",
        lambda text, title=None: "锚点产品",
    )
    deps = _deps("公司倡导诚信经营。", MockLlmClient([]))

    enrich_source(kb_id="kb-1", source_id="source-1", deps=deps, settings=_settings())

    assert calls and calls[0] == "锚点产品"
