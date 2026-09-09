from __future__ import annotations

from compiler.rule_extractor import RuleExtractor
from domains.generic.domain import register_generic_ontology
from knowledge.models import Claim
from ontology.ports import OntologyPort


class LoanFinanceDomain:
    name = "loan_finance"

    def register_ontology(self, ontology: OntologyPort) -> None:
        register_generic_ontology(ontology)

    def get_extractor(self) -> RuleExtractor:
        return RuleExtractor()

    def get_aliases(self) -> list[str]:
        return []

    def format_claim(self, claim: Claim) -> str:
        return f"{claim.subject}{claim.predicate}{claim.object}"

    def low_confidence_message(self) -> str:
        return "依据不足，无法根据现有知识库内容回答该问题。"

    def high_risk_predicates(self) -> list[str]:
        return []
