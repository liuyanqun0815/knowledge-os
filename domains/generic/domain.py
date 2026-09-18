from __future__ import annotations

from akos.application.ingest.extraction_spec import LlmExtractionSpec
from akos.application.ingest.rule_extractor import RuleExtractor
from knowledge.models import Claim
from akos.domain.ports.ontology import OntologyPort

_GENERIC_PREDICATES = [
    ("Concept", "相关", "Concept"),
    ("Concept", "定义", "Concept"),
    ("Concept", "属于", "Concept"),
]


def register_generic_ontology(ontology: OntologyPort) -> None:
    for subject_type, predicate, object_type in _GENERIC_PREDICATES:
        ontology.register_predicate(subject_type, predicate, object_type)


class GenericDomain:
    name = "generic"

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
            allowed_predicates=["规定", "适用于", "禁止", "要求"],
            entity_types=["Concept", "Policy"],
            few_shot_hints=[
                "正例：subject=具体政策或主题实体，predicate=规定，object=…",
                "反例：subject=属性词（禁止单独作 subject）",
            ],
        )
