from __future__ import annotations

import os

import pytest

from akos.application.ingest.llm_extractor import LlmExtractor
from akos.domains.corporate_culture.formatter import format_corporate_claim
from akos.domains.registry import load_domain
from akos.adapters.llm.client import LlmConfigError, OpenAiCompatibleClient
from infra.settings import Settings
from akos.domain.models.knowledge import Claim
from akos.adapters.ontology.memory import InMemoryOntology


def _sample_corporate_claim(**overrides: object) -> Claim:
    defaults = {
        "id": "c1",
        "family_id": "f1",
        "version": 1,
        "subject": "员工手册",
        "predicate": "禁止",
        "object": "加班文化",
        "subject_type": "Policy",
        "object_type": "Behavior",
        "confidence": 0.8,
        "status": "active",
        "valid_from": None,
        "valid_to": None,
        "source_ids": ["s1"],
    }
    defaults.update(overrides)
    return Claim(**defaults)


def test_openai_client_raises_without_key():
    client = OpenAiCompatibleClient(Settings(llm_api_key=""))
    assert client.is_configured is False
    with pytest.raises(LlmConfigError, match="AKOS_LLM_API_KEY"):
        client.chat_completions([{"role": "user", "content": "hi"}])


def test_llm_extractor_raises_without_key():
    client = OpenAiCompatibleClient(Settings(llm_api_key=""))
    extractor = LlmExtractor(client=client, domain="corporate_culture")
    with pytest.raises(LlmConfigError, match="AKOS_LLM_API_KEY"):
        extractor.extract("公司倡导诚信协作，禁止内部恶性竞争。")


def test_corporate_domain_registers_ontology():
    domain = load_domain("corporate_culture")
    ontology = InMemoryOntology()
    domain.register_ontology(ontology)
    assert ontology.resolve_entity_type("诚信") == "Value"
    assert ontology.resolve_entity_type("加班文化") == "Behavior"
    assert ontology.normalize_term("价值观") == "诚信"
    assert "倡导" in ontology.allowed_predicates("Value", "Behavior")
    assert "禁止" in ontology.allowed_predicates("Policy", "Behavior")
    assert ontology.validate_claim("Policy", "适用于", "Department")


def test_corporate_domain_uses_rule_extractor():
    from akos.application.ingest.rule_extractor import RuleExtractor

    domain = load_domain("corporate_culture")
    extractor = domain.get_extractor()
    assert isinstance(extractor, RuleExtractor)
    claims = extractor.extract("员工手册倡导诚信协作，禁止贿赂。")
    preds = {c.predicate for c in claims}
    assert "倡导" in preds
    assert "禁止" in preds


def test_corporate_format_claim():
    claim = _sample_corporate_claim()
    assert format_corporate_claim(claim) == "员工手册禁止加班文化"
    advocate = _sample_corporate_claim(subject="诚信", predicate="倡导", object="协作", subject_type="Value", object_type="Value")
    assert format_corporate_claim(advocate) == "诚信倡导协作"


def test_llm_extractor_parses_json_response():
    client = OpenAiCompatibleClient(Settings(llm_api_key="test-key"))
    extractor = LlmExtractor(client=client, domain="corporate_culture")

    def fake_chat(messages, *, temperature=0.0, timeout=60.0):
        return (
            '[{"subject":"员工手册","predicate":"倡导","object":"诚信",'
            '"confidence":0.9,"quote":"员工手册倡导诚信"}]'
        )

    client.chat_completions = fake_chat  # type: ignore[method-assign]
    text = "员工手册倡导诚信协作。"
    claims = extractor.extract(text)
    assert len(claims) == 1
    assert claims[0].subject == "员工手册"
    assert claims[0].predicate == "倡导"
    assert claims[0].object == "诚信"


@pytest.mark.skipif(os.getenv("AKOS_LLM_INTEGRATION") != "1", reason="optional LLM integration; set AKOS_LLM_INTEGRATION=1")
def test_llm_extractor_integration_with_real_key():
    extractor = LlmExtractor(domain="corporate_culture")
    text = "员工手册倡导诚信协作，禁止内部恶性竞争，适用于研发部。"
    claims = extractor.extract(text)
    assert claims, "expected LLM to extract at least one claim"
