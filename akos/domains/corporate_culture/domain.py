from __future__ import annotations

from akos.application.ingest.extraction_spec import LlmExtractionSpec
from akos.application.ingest.llm_extractor import create_corporate_extractor
from akos.domain.ports.compiler import ExtractorPort
from akos.domains.corporate_culture.formatter import format_corporate_claim
from akos.domains.corporate_culture.seed import register_corporate_culture
from akos.domain.models.knowledge import Claim
from akos.domain.ports.ontology import OntologyPort


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

    def llm_extraction_spec(self) -> LlmExtractionSpec:
        return LlmExtractionSpec(
            allowed_predicates=["倡导", "禁止", "适用于"],
            entity_types=["Value", "Behavior", "Policy", "Department"],
        )
