from __future__ import annotations

from typing import Protocol, runtime_checkable

from akos.domain.ports.compiler import ExtractorPort
from akos.domain.ports.ontology import OntologyPort
from akos.application.ingest.extraction_spec import LlmExtractionSpec
from knowledge.models import Claim


@runtime_checkable
class DomainPort(Protocol):
    name: str

    def register_ontology(self, ontology: OntologyPort) -> None: ...

    def get_extractor(self) -> ExtractorPort: ...

    def get_aliases(self) -> list[str]: ...

    def format_claim(self, claim: Claim) -> str: ...

    def low_confidence_message(self) -> str: ...

    def high_risk_predicates(self) -> list[str]: ...

    def llm_extraction_spec(self) -> LlmExtractionSpec: ...
