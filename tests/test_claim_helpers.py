from __future__ import annotations

from datetime import datetime, timezone

from admin_api.claim_helpers import list_filtered_claims
from knowledge.memory_repo import InMemoryKnowledge
from knowledge.models import Claim


def _claim(*, claim_id: str, subject: str, predicate: str, obj: str, status: str = "active") -> Claim:
    return Claim(
        id=claim_id,
        family_id=f"f-{claim_id}",
        version=1,
        subject=subject,
        predicate=predicate,
        object=obj,
        subject_type="Concept",
        object_type="Concept",
        confidence=0.9,
        status=status,
        valid_from=datetime.now(timezone.utc),
        valid_to=None,
        source_ids=["s1"],
    )


def test_list_filtered_claims_fuzzy_matches_subject_predicate_object():
    knowledge = InMemoryKnowledge()
    knowledge.append_claim(
        _claim(
            claim_id="c1",
            subject="青银理财璀璨人生成就系列",
            predicate="本金损失风险",
            obj="青银理财不保证本金及收益",
        )
    )
    knowledge.append_claim(
        _claim(
            claim_id="c2",
            subject="个人信用贷款",
            predicate="定义",
            obj="无需抵押担保的贷款产品",
        )
    )

    by_subject = list_filtered_claims(knowledge, subject="璀璨人生")
    assert [claim.id for claim in by_subject] == ["c1"]

    by_predicate = list_filtered_claims(knowledge, predicate="损失")
    assert [claim.id for claim in by_predicate] == ["c1"]

    by_object = list_filtered_claims(knowledge, object="不保证本金")
    assert [claim.id for claim in by_object] == ["c1"]

    combined = list_filtered_claims(knowledge, subject="青银", predicate="风险", object="收益")
    assert [claim.id for claim in combined] == ["c1"]

    miss = list_filtered_claims(knowledge, subject="璀璨", predicate="定义")
    assert miss == []
