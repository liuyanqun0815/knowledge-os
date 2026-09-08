from knowledge.models import TextSpan

from evidence.ports import EvidenceBundle


class InMemoryEvidence:
    def __init__(self) -> None:
        self._bindings: dict[str, list[dict]] = {}

    def bind(self, claim_id: str, source_id: str, span: TextSpan, weight: float) -> None:
        if claim_id not in self._bindings:
            self._bindings[claim_id] = []
        self._bindings[claim_id].append(
            {
                "source_id": source_id,
                "start": span.start,
                "end": span.end,
                "quote": span.quote,
                "weight": weight,
            }
        )

    def explain(self, claim_ids: list[str]) -> EvidenceBundle:
        items: list[dict] = []
        weights: list[float] = []
        for claim_id in claim_ids:
            for binding in self._bindings.get(claim_id, []):
                items.append(binding)
                weights.append(binding["weight"])
        confidence = sum(weights) / len(weights) if weights else 0.0
        conclusion = "; ".join(claim_ids)
        return EvidenceBundle(conclusion=conclusion, items=items, confidence=confidence)
