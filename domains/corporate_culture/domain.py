from __future__ import annotations

from compiler.llm_extractor import create_corporate_extractor
from compiler.ports import ExtractorPort
from domains.corporate_culture.formatter import format_corporate_claim
from domains.corporate_culture.seed import register_corporate_culture
from knowledge.models import Claim
from ontology.ports import OntologyPort


class CorporateCultureDomain:
    name = "corporate_culture"

    def register_ontology(self, ontology: OntologyPort) -> None:
        register_corporate_culture(ontology)

    def get_extractor(self) -> ExtractorPort:
        return create_corporate_extractor()

    def get_aliases(self) -> list[str]:
        return ["价值观", "文化手册", "员工手册"]

    def format_claim(self, claim: Claim) -> str:
        return format_corporate_claim(claim)

    def low_confidence_message(self) -> str:
        return "依据不足，无法根据现有知识库内容回答该问题。"

    def high_risk_predicates(self) -> list[str]:
        return []
