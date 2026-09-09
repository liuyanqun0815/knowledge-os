from __future__ import annotations

import json
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from compiler.enrichment import enrich_source
from compiler.extraction_spec import LlmExtractionSpec
from compiler.ports import ExtractedClaim
from compiler.service import KnowledgeCompiler
from evidence.memory_repo import InMemoryEvidence
from graph.memory_repo import InMemoryGraph
from infra.settings import Settings
from knowledge.memory_repo import InMemoryKnowledge
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
