import os
from datetime import datetime, timezone

import pytest

from akos.domain.models.knowledge import Claim, Source
from tests.conftest import pg_enabled

pytestmark = pytest.mark.skipif(
    not pg_enabled(),
    reason="requires AKOS_USE_PG=true",
)


def _sample_claim(source_ids: list[str]) -> Claim:
    return Claim(
        id="c-iso-1",
        family_id="f-iso-1",
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
        source_ids=source_ids,
    )


def _sample_source(source_id: str = "s1") -> Source:
    return Source(
        id=source_id,
        title="policy",
        type="policy",
        uri="file://p",
        version="1",
        created_at=datetime.now(timezone.utc),
        status="ready",
    )


def test_two_kbs_claims_do_not_leak(pg_kb_repo, pg_engine):
    from akos.adapters.persistence.pg_knowledge import PgKnowledge

    kb_a = pg_kb_repo.create(name="A", domain_type="ecommerce_cs", description="")
    kb_b = pg_kb_repo.create(name="B", domain_type="ecommerce_cs", description="")
    repo_a = PgKnowledge(pg_engine, kb_a.id)
    repo_b = PgKnowledge(pg_engine, kb_b.id)

    repo_a.save_source(_sample_source("s1"))
    repo_a.append_claim(_sample_claim(source_ids=["s1"]))

    assert repo_a.get_active_claims("七天无理由")
    assert not repo_b.get_active_claims("七天无理由")


def test_two_kbs_sources_do_not_leak(pg_kb_repo, pg_engine):
    from akos.adapters.persistence.pg_knowledge import PgKnowledge

    kb_a = pg_kb_repo.create(name="A-src", domain_type="ecommerce_cs", description="")
    kb_b = pg_kb_repo.create(name="B-src", domain_type="ecommerce_cs", description="")
    repo_a = PgKnowledge(pg_engine, kb_a.id)
    repo_b = PgKnowledge(pg_engine, kb_b.id)

    repo_a.save_source(_sample_source("shared-source-id"))
    repo_a.save_source_text("shared-source-id", "kb-a text")

    assert repo_a.get_source("shared-source-id") is not None
    assert repo_a.get_source_text("shared-source-id") == "kb-a text"
    assert repo_b.get_source("shared-source-id") is None
    assert repo_b.get_source_text("shared-source-id") is None


def test_two_kbs_can_share_same_source_id(pg_kb_repo, pg_engine):
    from akos.adapters.persistence.pg_knowledge import PgKnowledge

    kb_a = pg_kb_repo.create(name="A-share-sid", domain_type="ecommerce_cs", description="")
    kb_b = pg_kb_repo.create(name="B-share-sid", domain_type="ecommerce_cs", description="")
    repo_a = PgKnowledge(pg_engine, kb_a.id)
    repo_b = PgKnowledge(pg_engine, kb_b.id)

    repo_a.save_source(_sample_source("理财产品汇总"))
    repo_a.save_source_text("理财产品汇总", "kb-a body")
    repo_a.update_source_status("理财产品汇总", "pending")

    repo_b.save_source(_sample_source("理财产品汇总"))
    repo_b.save_source_text("理财产品汇总", "kb-b body")
    repo_b.update_source_status("理财产品汇总", "running")

    assert repo_a.get_source_text("理财产品汇总") == "kb-a body"
    assert repo_b.get_source_text("理财产品汇总") == "kb-b body"
    assert repo_a.get_source("理财产品汇总").status == "pending"
    assert repo_b.get_source("理财产品汇总").status == "running"


def test_two_kbs_quarantine_do_not_leak(pg_kb_repo, pg_engine):
    from akos.adapters.persistence.pg_knowledge import PgKnowledge

    kb_a = pg_kb_repo.create(name="A-q", domain_type="ecommerce_cs", description="")
    kb_b = pg_kb_repo.create(name="B-q", domain_type="ecommerce_cs", description="")
    repo_a = PgKnowledge(pg_engine, kb_a.id)
    repo_b = PgKnowledge(pg_engine, kb_b.id)

    repo_a.add_quarantine("test", {"claim_id": "c1"})

    assert len(repo_a.list_quarantine()) == 1
    assert not repo_b.list_quarantine()
