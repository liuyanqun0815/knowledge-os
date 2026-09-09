from __future__ import annotations

from knowledge.models import Claim
from knowledge.ports import KnowledgePort


def sorted_claim_history(knowledge: KnowledgePort, family_id: str) -> list[Claim]:
    claims = knowledge.get_claim_history(family_id)
    visible = [claim for claim in claims if claim.status != "staging"]
    return sorted(visible, key=lambda claim: claim.version)
