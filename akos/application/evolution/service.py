from __future__ import annotations

from datetime import datetime

from akos.domain.models.knowledge import Claim
from akos.domain.ports.knowledge import KnowledgePort

from akos.application.evolution.applier import KnowledgeApplier
from akos.application.evolution.differ import KnowledgeDiffer
from akos.domain.ports.evolution import ApplyReport, KnowledgeDiff


class EvolutionService:
    """Facade implementing :class:`EvolutionPort` over differ + applier + knowledge."""

    def __init__(self, knowledge: KnowledgePort) -> None:
        self._knowledge = knowledge
        self._differ = KnowledgeDiffer(knowledge)
        self._applier = KnowledgeApplier(knowledge)

    def diff_sources(self, old_source_id: str, new_source_id: str) -> KnowledgeDiff:
        return self._differ.diff_sources(old_source_id, new_source_id)

    def apply_diff(self, diff: KnowledgeDiff) -> ApplyReport:
        return self._applier.apply_diff(diff)

    def as_of(self, query_time: datetime, claim_family_id: str) -> Claim | None:
        return self._knowledge.as_of(query_time, claim_family_id)
