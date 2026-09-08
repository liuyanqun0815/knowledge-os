import os

import pytest

from knowledge.models import Claim, Source
from tests.conftest import pg_enabled

pytestmark = pytest.mark.skipif(
    not pg_enabled(),
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


@pytest.fixture
def pg_knowledge(pg_engine, pg_kb_repo):
    from infra.pg_repos import PgKnowledge

    kb = pg_kb_repo.create(name="pg-knowledge-test", domain_type="ecommerce_cs", description="")
    return PgKnowledge(pg_engine, kb.id)


def test_pg_append_claim_roundtrip(pg_knowledge):
    from datetime import datetime, timezone

    pg_knowledge.save_source(_source())
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
    pg_knowledge.append_claim(c1)
    fetched = pg_knowledge.get_claim("c-pg-1")
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
    pg_knowledge.mark_superseded("c-pg-1", datetime.now(timezone.utc))
    pg_knowledge.append_claim(c2)

    active = pg_knowledge.get_active_claims("七天无理由", "运费承担方")
    assert len(active) == 1
    assert active[0].object == "平台"

    hist = pg_knowledge.get_claim_history("f-pg-1")
    assert len(hist) >= 2
    assert {c.id for c in hist} >= {"c-pg-1", "c-pg-2"}


def test_pg_mark_superseded_does_not_overwrite_object(pg_knowledge):
    from datetime import datetime, timezone

    pg_knowledge.save_source(_source("s-pg-2"))
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
    pg_knowledge.append_claim(c1)
    pg_knowledge.mark_superseded("c-pg-super-1", datetime.now(timezone.utc))

    updated = pg_knowledge.get_claim("c-pg-super-1")
    assert updated is not None
    assert updated.status == "superseded"
    assert updated.object == "7"
    assert updated.valid_to is not None
