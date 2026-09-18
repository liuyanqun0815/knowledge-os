from __future__ import annotations

import uuid
from datetime import datetime, timezone

from knowledge.models import Claim
from akos.domain.ports.knowledge import KnowledgePort

from akos.domain.ports.evolution import ApplyReport, KnowledgeDiff


class KnowledgeApplier:
    def __init__(self, knowledge: KnowledgePort) -> None:
        self._knowledge = knowledge

    def apply_diff(self, diff: KnowledgeDiff) -> ApplyReport:
        now = datetime.now(timezone.utc)
        claims_activated: list[str] = []
        claims_superseded: list[str] = []
        events_created: list[str] = []
        errors: list[str] = []

        for old_id, new_id in diff.claims_superseded:
            staging = self._knowledge.get_claim(new_id)
            if staging is None:
                errors.append(f"staging claim not found: {new_id}")
                continue
            self._knowledge.mark_superseded(old_id, valid_to=now)
            claims_superseded.append(old_id)
            active = self._activate_staging_claim(staging, valid_from=now)
            self._knowledge.append_claim(active)
            claims_activated.append(active.id)
            events_created.append(self._stub_event("policy_changed", diff.source_new_id))

        for claim_id in diff.claims_added:
            staging = self._knowledge.get_claim(claim_id)
            if staging is None:
                errors.append(f"staging claim not found: {claim_id}")
                continue
            active = self._activate_staging_claim(staging, valid_from=now)
            self._knowledge.append_claim(active)
            claims_activated.append(active.id)
            events_created.append(self._stub_event("claim_added", diff.source_new_id))

        return ApplyReport(
            source_old_id=diff.source_old_id,
            source_new_id=diff.source_new_id,
            claims_activated=claims_activated,
            claims_superseded=claims_superseded,
            events_created=events_created,
            errors=errors,
        )

    def _activate_staging_claim(self, staging: Claim, valid_from: datetime) -> Claim:
        history = self._knowledge.get_claim_history(staging.family_id)
        max_version = max((c.version for c in history), default=0)
        return Claim(
            id=str(uuid.uuid4()),
            family_id=staging.family_id,
            version=max_version + 1,
            subject=staging.subject,
            predicate=staging.predicate,
            object=staging.object,
            subject_type=staging.subject_type,
            object_type=staging.object_type,
            confidence=staging.confidence,
            status="active",
            valid_from=valid_from,
            valid_to=None,
            source_ids=list(staging.source_ids),
        )

    @staticmethod
    def _stub_event(event_type: str, source_id: str) -> str:
        return f"{event_type}:{source_id}:{uuid.uuid4()}"
