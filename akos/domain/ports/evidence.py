from dataclasses import dataclass
from typing import Any, Protocol

from akos.domain.models.knowledge import TextSpan


@dataclass
class EvidenceBundle:
    conclusion: str
    items: list[dict[str, Any]]
    confidence: float


class EvidencePort(Protocol):
    def bind(self, claim_id: str, source_id: str, span: TextSpan, weight: float) -> None: ...

    def explain(self, claim_ids: list[str]) -> EvidenceBundle: ...
