from __future__ import annotations

from compiler.extraction_spec import LlmExtractionSpec
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

    def llm_extraction_spec(self) -> LlmExtractionSpec:
        return LlmExtractionSpec(
            allowed_predicates=["适用客户", "利率_年化", "最高额度", "还款方式"],
            entity_types=["Product", "RateRule", "RiskLevel"],
            few_shot_hints=[
                "正例（本段有主体）：文段写「个人信用贷款最高额度30万」→ subject=个人信用贷款，predicate=最高额度，object=30万",
                "正例（本段无主体、回退锚点）：文段只写「还款方式：等额本息」且 document_anchor=青银理财成就系列（低波共享）→ subject=青银理财成就系列（低波共享），predicate=还款方式，object=等额本息",
                "反例：subject=还款方式（禁止：属性词不可单独作 subject）",
                "反例：本段已出现「个人信用贷款」时仍强制用文件名作 subject",
            ],
        )
