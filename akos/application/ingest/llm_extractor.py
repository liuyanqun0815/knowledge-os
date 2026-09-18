from __future__ import annotations

from akos.application.ingest.domain_llm_extractor import DomainLlmExtractor
from akos.application.ingest.extraction_spec import LlmExtractionSpec
from akos.domain.ports.compiler import ExtractedClaim, ExtractorPort
from akos.adapters.llm.client import OpenAiCompatibleClient


def _corporate_spec() -> LlmExtractionSpec:
    return LlmExtractionSpec(
        allowed_predicates=["倡导", "禁止", "适用于"],
        entity_types=["Value", "Behavior", "Policy", "Department"],
    )


class LlmExtractor(DomainLlmExtractor):
    """Backward-compatible corporate culture LLM extractor."""

    def __init__(
        self,
        client: OpenAiCompatibleClient | None = None,
        domain: str = "corporate_culture",
    ) -> None:
        self._domain = domain
        super().__init__(client or OpenAiCompatibleClient(), _corporate_spec())

    def extract(self, text: str, **kwargs) -> list[ExtractedClaim]:
        if self._domain != "corporate_culture":
            return []
        return super().extract(text, **kwargs)


def create_corporate_extractor(client: OpenAiCompatibleClient | None = None) -> ExtractorPort:
    """Create the legacy corporate extractor backed by a domain extraction spec."""
    return LlmExtractor(client=client, domain="corporate_culture")
