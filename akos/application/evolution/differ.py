from __future__ import annotations

from knowledge.ports import KnowledgePort

from evolution.ports import KnowledgeDiff


class KnowledgeDiffer:
    def __init__(self, knowledge: KnowledgePort) -> None:
        self._knowledge = knowledge

    def diff_sources(self, old_source_id: str, new_source_id: str) -> KnowledgeDiff:
        old_claims = [
            c for c in self._knowledge.get_claims_for_source(old_source_id) if c.status == "active"
        ]
        new_claims = [
            c for c in self._knowledge.get_claims_for_source(new_source_id) if c.status == "staging"
        ]

        old_by_family = {c.family_id: c for c in old_claims}
        new_by_family = {c.family_id: c for c in new_claims}

        claims_added: list[str] = []
        claims_superseded: list[tuple[str, str]] = []
        entities_changed: list[str] = []

        for family_id, new_claim in new_by_family.items():
            old_claim = old_by_family.get(family_id)
            if old_claim is None:
                claims_added.append(new_claim.id)
                continue
            if old_claim.object != new_claim.object or old_claim.predicate != new_claim.predicate:
                claims_superseded.append((old_claim.id, new_claim.id))
                if old_claim.object != new_claim.object:
                    entities_changed.append(new_claim.object)

        return KnowledgeDiff(
            source_old_id=old_source_id,
            source_new_id=new_source_id,
            claims_added=claims_added,
            claims_superseded=claims_superseded,
            entities_changed=entities_changed,
        )
