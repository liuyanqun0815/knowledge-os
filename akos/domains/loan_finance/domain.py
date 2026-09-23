from __future__ import annotations

from akos.application.ingest.extraction_spec import LlmExtractionSpec
from akos.domains.loan_finance.rules import LoanRuleExtractor
from akos.domains.loan_finance.seed import ENTITY_SEEDS, PREDICATES, register_loan_finance
from akos.domain.models.knowledge import Claim
from akos.domain.ports.ontology import OntologyPort


class LoanFinanceDomain:
    name = "loan_finance"

    def register_ontology(self, ontology: OntologyPort) -> None:
        register_loan_finance(ontology)

    def get_extractor(self) -> LoanRuleExtractor:
        return LoanRuleExtractor()

    def get_aliases(self) -> list[str]:
        from akos.domains.loan_finance.seed import ALIASES

        return list(ALIASES.keys())

    def format_claim(self, claim: Claim) -> str:
        if claim.predicate == "利率_年化":
            return f"{claim.subject}年化利率为{claim.object}"
        if claim.predicate == "最高额度":
            return f"{claim.subject}最高额度为{claim.object}"
        if claim.predicate == "还款方式":
            return f"{claim.subject}还款方式为{claim.object}"
        if claim.predicate == "适用客户":
            return f"{claim.subject}适用于{claim.object}"
        if claim.predicate == "贷款期限":
            return f"{claim.subject}贷款期限为{claim.object}"
        if claim.predicate == "担保方式":
            return f"{claim.subject}担保方式为{claim.object}"
        if claim.predicate == "贷款用途":
            return f"{claim.subject}贷款用途为{claim.object}"
        if claim.predicate == "起息说明":
            return f"{claim.subject}起息说明：{claim.object}"
        return f"{claim.subject}{claim.predicate}{claim.object}"

    def low_confidence_message(self) -> str:
        return "依据不足，无法根据现有知识库内容回答该问题。"

    def high_risk_predicates(self) -> list[str]:
        return ["利率_年化", "最高额度", "适用客户"]

    def llm_extraction_spec(self) -> LlmExtractionSpec:
        predicates = sorted({predicate for _, predicate, _ in PREDICATES})
        entity_types = sorted(set(ENTITY_SEEDS.values()) | {"Product", "Concept", "RateRule", "RiskLevel"})
        return LlmExtractionSpec(
            allowed_predicates=predicates,
            entity_types=entity_types,
            few_shot_hints=[
                "正例：个人信用贷款最高额度30万 → subject=个人信用贷款，predicate=最高额度，object=30万",
                "正例：单户贷款额度不超过200万元 → predicate=最高额度，object=200万元",
                "正例：年化利率3.15%起 → predicate=利率_年化，object=3.15%起",
                "正例：年化综合融资成本3%-19.8% → predicate=利率_年化",
                "正例：还款方式：等额本息、等额本金 → predicate=还款方式（可回退 document_anchor）",
                "正例：贷款对象：年满18周岁… → predicate=适用客户",
                "正例：贷款期限最长不超过五年 → predicate=贷款期限，object=五年",
                "正例：担保方式采取抵押、保证、信用 → predicate=担保方式",
                "正例：贷款可用于住房装修、购车…；不得用于购房/投资 → predicate=贷款用途",
                "正例：自贷款发放日起计息 → predicate=起息说明",
                "反例：subject=还款方式 / 利率 / 额度（属性词不可作 subject）",
                "反例：本段已出现产品名时仍只用文件名作 subject",
            ],
        )
