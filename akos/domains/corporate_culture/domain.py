from __future__ import annotations

from akos.application.ingest.extraction_spec import LlmExtractionSpec
from akos.application.ingest.rule_extractor import RuleExtractor
from akos.domains.corporate_culture.formatter import format_corporate_claim
from akos.domains.corporate_culture.rules import CULTURE_RULES
from akos.domains.corporate_culture.seed import register_corporate_culture
from akos.domain.models.knowledge import Claim
from akos.domain.ports.ontology import OntologyPort


class CorporateCultureDomain:
    name = "corporate_culture"

    def register_ontology(self, ontology: OntologyPort) -> None:
        register_corporate_culture(ontology)

    def get_extractor(self) -> RuleExtractor:
        # 规则层做确定性抽取；LLM 混合抽取仍走 llm_extraction_spec
        return RuleExtractor(CULTURE_RULES)

    def get_aliases(self) -> list[str]:
        from akos.domains.corporate_culture.seed import ALIASES

        return list(ALIASES.keys())

    def format_claim(self, claim: Claim) -> str:
        return format_corporate_claim(claim)

    def low_confidence_message(self) -> str:
        return "依据不足，无法根据现有知识库内容回答该问题。"

    def high_risk_predicates(self) -> list[str]:
        return ["禁止"]

    def llm_extraction_spec(self) -> LlmExtractionSpec:
        return LlmExtractionSpec(
            allowed_predicates=["倡导", "禁止", "适用于"],
            entity_types=["Value", "Behavior", "Policy", "Department", "Concept"],
            few_shot_hints=[
                "正例：员工手册倡导诚信协作 → subject=员工手册，predicate=倡导，object=诚信协作",
                "正例：公司倡导廉洁诚信 → predicate=倡导，object=廉洁诚信",
                "正例：鼓励员工相互尊重 → predicate=倡导",
                "正例：禁止贿赂与利益冲突 → predicate=禁止，object=贿赂与利益冲突",
                "正例：不得泄露公司保密信息 → predicate=禁止",
                "正例：严格禁止对举报人进行打击报复 → predicate=禁止",
                "正例：行为准则适用于全体员工及实习生 → predicate=适用于，object=全体员工及实习生",
                "正例：适用范围：正式员工、实习生、外包人员 → predicate=适用于",
                "反例：subject=禁止 / 倡导（谓词不可作 subject）",
                "反例：把整章标题当作唯一 object，而不拆具体行为",
            ],
        )
