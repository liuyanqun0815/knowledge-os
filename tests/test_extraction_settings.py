from __future__ import annotations

import pytest

from compiler.extraction_spec import LlmExtractionSpec
from domains.registry import load_domain
from infra.settings import Settings


def test_extraction_settings_defaults():
    s = Settings(
        _env_file=None,
        llm_api_key="",
    )
    assert s.extract_rules is True
    assert s.extract_llm is True
    assert s.chunk_max_chars == 3000
    assert s.chunk_max_per_doc == 40
    assert s.extract_min_confidence == 0.5


def test_llm_extraction_spec_dataclass():
    spec = LlmExtractionSpec(
        allowed_predicates=["适用类目"],
        entity_types=["RefundRule"],
        few_shot_hints=["示例：七天无理由适用类目为非定制商品"],
    )
    assert spec.allowed_predicates == ["适用类目"]
    assert spec.entity_types == ["RefundRule"]
    assert spec.prompt_locale == "zh"
    assert spec.few_shot_hints == ["示例：七天无理由适用类目为非定制商品"]


@pytest.mark.parametrize("domain_type", ["ecommerce_cs", "corporate_culture", "generic", "loan_finance"])
def test_domain_llm_extraction_spec(domain_type: str):
    domain = load_domain(domain_type)
    spec = domain.llm_extraction_spec()
    assert isinstance(spec, LlmExtractionSpec)
    assert isinstance(spec.allowed_predicates, list)
    assert isinstance(spec.entity_types, list)
