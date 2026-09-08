import os

import pytest

from knowledge.models import Claim, Source

pytestmark = pytest.mark.skipif(
    os.getenv("AKOS_USE_PG", "false").lower() != "true",
    reason="AKOS_USE_PG not enabled",
)


def _source(sid: str = "s-pg-1") -> Source:
    from datetime import datetime, timezone

    return Source(
        id=sid,
        title="policy",
        type="policy",
        uri="file://p",
        version="1",
        created_at=datetime.now(timezone.utc),
        status="ready",
    )


def test_pg_append_claim_roundtrip():
    from datetime import datetime, timezone

    from infra.bootstrap import build_pg_knowledge

    repo = build_pg_knowledge()
    repo.save_source(_source())
    c1 = Claim(
        id="c-pg-1",
        family_id="f-pg-1",
        version=1,
        subject="七天无理由",
        predicate="运费承担方",
        object="买家",
        subject_type="RefundRule",
        object_type="Concept",
        confidence=0.9,
        status="active",
        valid_from=datetime.now(timezone.utc),
        valid_to=None,
        source_ids=["s-pg-1"],
    )
    repo.append_claim(c1)
    fetched = repo.get_claim("c-pg-1")
    assert fetched is not None
    assert fetched.object == "买家"
    assert fetched.status == "active"

    c2 = Claim(
        id="c-pg-2",
        family_id="f-pg-1",
        version=2,
        subject="七天无理由",
        predicate="运费承担方",
        object="平台",
        subject_type="RefundRule",
        object_type="Concept",
        confidence=0.95,
        status="active",
        valid_from=datetime.now(timezone.utc),
        valid_to=None,
        source_ids=["s-pg-1"],
    )
    repo.mark_superseded("c-pg-1", datetime.now(timezone.utc))
    repo.append_claim(c2)

    active = repo.get_active_claims("七天无理由", "运费承担方")
    assert len(active) == 1
    assert active[0].object == "平台"

    hist = repo.get_claim_history("f-pg-1")
    assert len(hist) >= 2
    assert {c.id for c in hist} >= {"c-pg-1", "c-pg-2"}


def test_pg_mark_superseded_does_not_overwrite_object():
    from datetime import datetime, timezone

    from infra.bootstrap import build_pg_knowledge

    repo = build_pg_knowledge()
    repo.save_source(_source("s-pg-2"))
    c1 = Claim(
        id="c-pg-super-1",
        family_id="f-pg-super",
        version=1,
        subject="七天无理由",
        predicate="退货时限_天",
        object="7",
        subject_type="RefundRule",
        object_type="Concept",
        confidence=0.9,
        status="active",
        valid_from=datetime.now(timezone.utc),
        valid_to=None,
        source_ids=["s-pg-2"],
    )
    repo.append_claim(c1)
    repo.mark_superseded("c-pg-super-1", datetime.now(timezone.utc))

    updated = repo.get_claim("c-pg-super-1")
    assert updated is not None
    assert updated.status == "superseded"
    assert updated.object == "7"
    assert updated.valid_to is not None
