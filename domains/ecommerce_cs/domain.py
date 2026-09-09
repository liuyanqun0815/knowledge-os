from __future__ import annotations

from compiler.extraction_spec import LlmExtractionSpec
from compiler.rule_extractor import RuleExtractor
from domains.ecommerce_cs.formatter import format_ecommerce_claim
from domains.ecommerce_cs.seed import register_ecommerce_cs
from knowledge.models import Claim
from ontology.ports import OntologyPort


class EcommerceCsDomain:
    name = "ecommerce_cs"

    def register_ontology(self, ontology: OntologyPort) -> None:
        register_ecommerce_cs(ontology)

    def get_extractor(self) -> RuleExtractor:
        return RuleExtractor()

    def get_aliases(self) -> list[str]:
        return ["7天无理由", "七天无理由退货", "无理由退货", "七天无理由"]

    def format_claim(self, claim: Claim) -> str:
        return format_ecommerce_claim(claim)

    def low_confidence_message(self) -> str:
        return "依据不足，无法根据现有知识库内容回答该问题。"

    def high_risk_predicates(self) -> list[str]:
        return ["运费承担方", "退货时限_天"]

    def llm_extraction_spec(self) -> LlmExtractionSpec:
        return LlmExtractionSpec(
            allowed_predicates=[],
            entity_types=[],
        )
