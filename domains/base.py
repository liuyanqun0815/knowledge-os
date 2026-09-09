from __future__ import annotations

from typing import Protocol, runtime_checkable

from compiler.ports import ExtractorPort
from knowledge.models import Claim
from ontology.ports import OntologyPort


@runtime_checkable
class DomainPort(Protocol):
    name: str

    def register_ontology(self, ontology: OntologyPort) -> None: ...

    def get_extractor(self) -> ExtractorPort: ...

    def get_aliases(self) -> list[str]: ...

    def format_claim(self, claim: Claim) -> str: ...

    def low_confidence_message(self) -> str: ...

    def high_risk_predicates(self) -> list[str]: ...
