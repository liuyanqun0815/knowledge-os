from datetime import datetime, timezone

import pytest

from knowledge.models import Claim, Source, TextSpan
from tests.conftest import pg_enabled

pytestmark = pytest.mark.skipif(
    not pg_enabled(),
    reason="requires AKOS_USE_PG=true",
)


def _sample_source(source_id: str = "s-gem-1") -> Source:
    return Source(
        id=source_id,
        title="policy",
        type="policy",
        uri="file://p",
        version="1",
        created_at=datetime.now(timezone.utc),
        status="ready",
    )


def _sample_claim(claim_id: str = "c-gem-1", source_ids: list[str] | None = None) -> Claim:
    return Claim(
        id=claim_id,
        family_id="f-gem-1",
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
        source_ids=source_ids or ["s-gem-1"],
    )


def test_pg_graph_upsert_and_neighbors(pg_kb_repo, pg_engine):
    from akos.adapters.persistence.pg_graph import PgGraph

    kb = pg_kb_repo.create(name="graph-test", domain_type="ecommerce_cs", description="")
    graph = PgGraph(pg_engine, kb.id)

    graph.upsert_entity("e_rule", "RefundRule", {"name": "七天无理由"})
    graph.upsert_entity("e_cat", "Category", {"name": "非定制商品"})
    graph.upsert_relation("e_rule", "适用类目", "e_cat", {})

    edges = graph.neighbors("e_rule", predicates=["适用类目"], depth=1)
    assert len(edges) == 1
    assert edges[0].dst == "e_cat"


def test_two_kbs_graph_do_not_leak(pg_kb_repo, pg_engine):
    from akos.adapters.persistence.pg_graph import PgGraph

    kb_a = pg_kb_repo.create(name="A-graph", domain_type="ecommerce_cs", description="")
    kb_b = pg_kb_repo.create(name="B-graph", domain_type="ecommerce_cs", description="")
    graph_a = PgGraph(pg_engine, kb_a.id)
    graph_b = PgGraph(pg_engine, kb_b.id)

    graph_a.upsert_entity("e_rule", "RefundRule", {"name": "七天无理由"})
    graph_a.upsert_entity("e_cat", "Category", {"name": "非定制商品"})
    graph_a.upsert_relation("e_rule", "适用类目", "e_cat", {})

    assert len(graph_a.neighbors("e_rule")) == 1
    assert not graph_b.neighbors("e_rule")


def test_pg_evidence_bind_and_explain(pg_kb_repo, pg_engine):
    from akos.adapters.persistence.pg_evidence import PgEvidence
    from akos.adapters.persistence.pg_knowledge import PgKnowledge

    kb = pg_kb_repo.create(name="evidence-test", domain_type="ecommerce_cs", description="")
    knowledge = PgKnowledge(pg_engine, kb.id)
    evidence = PgEvidence(pg_engine, kb.id)

    knowledge.save_source(_sample_source())
    knowledge.append_claim(_sample_claim())

    evidence.bind("c-gem-1", "s-gem-1", TextSpan("s-gem-1", 0, 12, "定制商品不适用"), 0.95)
    bundle = evidence.explain(["c-gem-1"])

    assert bundle.confidence >= 0.9
    assert bundle.items[0]["quote"] == "定制商品不适用"


def test_two_kbs_evidence_do_not_leak(pg_kb_repo, pg_engine):
    from akos.adapters.persistence.pg_evidence import PgEvidence
    from akos.adapters.persistence.pg_knowledge import PgKnowledge

    kb_a = pg_kb_repo.create(name="A-evidence", domain_type="ecommerce_cs", description="")
    kb_b = pg_kb_repo.create(name="B-evidence", domain_type="ecommerce_cs", description="")
    knowledge_a = PgKnowledge(pg_engine, kb_a.id)
    evidence_a = PgEvidence(pg_engine, kb_a.id)
    evidence_b = PgEvidence(pg_engine, kb_b.id)

    knowledge_a.save_source(_sample_source())
    knowledge_a.append_claim(_sample_claim())
    evidence_a.bind("c-gem-1", "s-gem-1", TextSpan("s-gem-1", 0, 12, "定制商品不适用"), 0.95)

    assert evidence_a.explain(["c-gem-1"]).items
    assert not evidence_b.explain(["c-gem-1"]).items


def test_pg_memory_episode_recall(pg_kb_repo, pg_engine):
    from akos.adapters.persistence.pg_memory import PgMemory

    kb = pg_kb_repo.create(name="memory-test", domain_type="ecommerce_cs", description="")
    memory = PgMemory(pg_engine, kb.id)

    memory.remember_episode("sess1", {"q": "能否退货", "a": "看类目"})
    context = memory.recall("退货", "sess1")

    assert context.episodes


def test_two_kbs_memory_do_not_leak(pg_kb_repo, pg_engine):
    from akos.adapters.persistence.pg_memory import PgMemory

    kb_a = pg_kb_repo.create(name="A-memory", domain_type="ecommerce_cs", description="")
    kb_b = pg_kb_repo.create(name="B-memory", domain_type="ecommerce_cs", description="")
    memory_a = PgMemory(pg_engine, kb_a.id)
    memory_b = PgMemory(pg_engine, kb_b.id)

    memory_a.remember_episode("sess1", {"q": "能否退货", "a": "看类目"})

    assert memory_a.recall("退货", "sess1").episodes
    assert not memory_b.recall("退货", "sess1").episodes
