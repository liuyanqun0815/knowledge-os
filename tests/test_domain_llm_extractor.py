from __future__ import annotations

import json

import httpx
import pytest

from compiler.domain_llm_extractor import DomainLlmExtractor
from compiler.extraction_spec import LlmExtractionSpec
from compiler.llm_extractor import LlmExtractor, create_corporate_extractor
from domains.corporate_culture.domain import CorporateCultureDomain
from domains.loan_finance.domain import LoanFinanceDomain


class FakeLlmClient:
    is_configured = True

    def __init__(self, response: list[dict[str, object]]) -> None:
        self.response = response
        self.messages: list[dict[str, str]] = []

    def chat_completions(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.0,
        timeout: float = 60.0,
    ) -> str:
        self.messages = messages
        return json.dumps(self.response, ensure_ascii=False)


def _spec() -> LlmExtractionSpec:
    return LlmExtractionSpec(
        allowed_predicates=["倡导", "禁止", "适用于"],
        entity_types=["Value", "Behavior", "Policy", "Department"],
    )


def test_domain_llm_extractor_parses_claims_and_spans() -> None:
    client = FakeLlmClient(
        [
            {
                "subject": "公司",
                "predicate": "倡导",
                "object": "诚信经营",
                "confidence": 0.9,
                "quote": "公司倡导诚信经营",
            }
        ]
    )
    text = "公司倡导诚信经营。"

    claims = DomainLlmExtractor(client, _spec()).extract(text)

    assert len(claims) == 1
    assert claims[0].predicate == "倡导"
    assert claims[0].quote in text
    assert (claims[0].start, claims[0].end) == (0, 8)


def test_domain_llm_extractor_keeps_unknown_predicates() -> None:
    client = FakeLlmClient(
        [
            {
                "subject": "公司",
                "predicate": "鼓励",
                "object": "持续学习",
                "confidence": 0.8,
                "quote": "公司鼓励持续学习",
            }
        ]
    )

    claims = DomainLlmExtractor(client, _spec()).extract("公司鼓励持续学习。")

    assert [claim.predicate for claim in claims] == ["鼓励"]


def test_prompt_contains_spec_and_json_schema() -> None:
    client = FakeLlmClient([])

    DomainLlmExtractor(client, _spec()).extract("公司倡导诚信经营。")

    prompt = client.messages[0]["content"]
    assert '"allowed_predicates": ["倡导", "禁止", "适用于"]' in prompt
    assert '"entity_types": ["Value", "Behavior", "Policy", "Department"]' in prompt
    assert '"subject": "string"' in prompt
    assert '"start"' not in prompt


def test_loan_finance_hints_in_prompt() -> None:
    class FakeClient:
        is_configured = True

        def chat_completions(self, messages, **kwargs):
            return "[]"

    spec = LoanFinanceDomain().llm_extraction_spec()
    extractor = DomainLlmExtractor(FakeClient(), spec)
    prompt = extractor._build_prompt("x", document_anchor="青银理财成就系列（低波共享）")
    assert "正例" in prompt
    assert "反例" in prompt
    assert "还款方式（禁止" in prompt
    assert "few_shot_hints" in prompt


def test_build_prompt_includes_subject_rules_and_anchor() -> None:
    class FakeClient:
        is_configured = True

        def chat_completions(self, messages, **kwargs):
            return "[]"

    extractor = DomainLlmExtractor(
        FakeClient(),
        LlmExtractionSpec(
            allowed_predicates=["还款方式"],
            entity_types=["Product"],
        ),
    )
    prompt = extractor._build_prompt(
        "还款方式包含等额本息。",
        document_anchor="青银理财成就系列（低波共享）",
    )
    assert "还款方式" in prompt
    assert "青银理财成就系列（低波共享）" in prompt
    assert "document_anchor" in prompt
    assert "subject_priority" in prompt
    assert "bind_generic_deixis_to_document_anchor" in prompt
    assert "Prefer a concrete named entity" in prompt
    assert "generic/deictic" in prompt
    assert "Never let document_anchor override" in prompt
    assert "禁止单独使用属性词" in prompt or "属性词" in prompt


def test_open_prompt_uses_suggested_predicates_and_allows_novel() -> None:
    client = FakeLlmClient([])
    spec = LlmExtractionSpec(
        allowed_predicates=["倡导", "禁止"],
        entity_types=["Value", "Behavior"],
        open_predicates=True,
    )
    DomainLlmExtractor(client, spec).extract("公司倡导诚信经营。")
    prompt = client.messages[0]["content"]
    assert '"mode": "open"' in prompt
    assert '"suggested_predicates"' in prompt
    assert "不必限于" in prompt or "不必限" in prompt
    assert '"allowed_predicates"' not in prompt


def test_extract_rebinds_generic_subject_when_anchor_present() -> None:
    class FakeClient:
        is_configured = True

        def chat_completions(self, messages, **kwargs):
            return json.dumps(
                [
                    {
                        "subject": "本理财计划",
                        "predicate": "产品类型",
                        "object": "非保本浮动收益型",
                        "confidence": 0.9,
                        "quote": "本理财计划",
                    }
                ],
                ensure_ascii=False,
            )

    text = "本理财计划为非保本浮动收益型。"
    claims = DomainLlmExtractor(FakeClient(), _spec()).extract(
        text,
        document_anchor="青银理财成就系列（低波共享）",
    )
    assert len(claims) == 1
    assert claims[0].subject == "青银理财成就系列（低波共享）"

    class FlakyClient:
        is_configured = True

        def chat_completions(self, messages, **kwargs):
            raise httpx.ConnectError("SSL EOF")

    with pytest.raises(httpx.ConnectError):
        DomainLlmExtractor(FlakyClient(), _spec()).extract("公司倡导诚信经营。")

    client = FakeLlmClient(
        [
            {
                "subject": "公司",
                "predicate": "倡导",
                "object": "诚信经营",
                "confidence": 0.9,
                "quote": "不存在于原文",
            }
        ]
    )

    claims = DomainLlmExtractor(client, _spec()).extract("公司倡导诚信经营。")

    assert len(claims) == 1
    assert claims[0].quote == "不存在于原文"
    assert claims[0].quote not in "公司倡导诚信经营。"
    assert claims[0].start < 0


def test_corporate_spec_and_factory_remain_compatible() -> None:
    spec = CorporateCultureDomain().llm_extraction_spec()
    client = FakeLlmClient([])

    extractor = create_corporate_extractor(client)

    assert spec.allowed_predicates == ["倡导", "禁止", "适用于"]
    assert spec.entity_types == ["Value", "Behavior", "Policy", "Department"]
    assert isinstance(extractor, LlmExtractor)
    assert isinstance(extractor, DomainLlmExtractor)
