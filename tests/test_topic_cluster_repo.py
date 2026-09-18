from datetime import datetime, timezone

import pytest

from akos.adapters.persistence.knowledge_memory import InMemoryKnowledge
from akos.domain.models.knowledge import TopicCluster
from tests.conftest import pg_enabled


def _sample_cluster(*, cluster_id: str = "t1", kb_id: str = "default") -> TopicCluster:
    return TopicCluster(
        id=cluster_id,
        knowledge_base_id=kb_id,
        name="尺码选择",
        aliases=["尺码表"],
        chunk_ids=["c1"],
        claim_ids=["cl1"],
        source_ids=["s1"],
        summary=None,
        status="active",
        content_hash="abc",
        updated_at=datetime.now(timezone.utc),
    )


def test_memory_topic_cluster_roundtrip():
    repo = InMemoryKnowledge()
    cluster = _sample_cluster()
    repo.save_topic_clusters([cluster])
    listed = repo.list_topic_clusters()
    assert len(listed) == 1
    assert listed[0].name == "尺码选择"
    assert repo.get_topic_cluster("t1") is not None
    assert repo.get_topic_cluster("t1").name == "尺码选择"
    repo.mark_topic_clusters_stale()
    assert repo.list_topic_clusters() == []
    assert repo.list_topic_clusters(status="stale")[0].id == "t1"


def test_memory_topic_cluster_upsert():
    repo = InMemoryKnowledge()
    repo.save_topic_clusters([_sample_cluster()])
    updated = _sample_cluster()
    updated.name = "尺码指南"
    repo.save_topic_clusters([updated])
    listed = repo.list_topic_clusters()
    assert len(listed) == 1
    assert listed[0].name == "尺码指南"


@pytest.mark.skipif(not pg_enabled(), reason="AKOS_USE_PG not enabled")
def test_pg_topic_cluster_roundtrip(pg_engine, pg_kb_repo):
    from akos.adapters.persistence.pg_knowledge import PgKnowledge

    kb = pg_kb_repo.create(name="topic-cluster-pg", domain_type="ecommerce_cs", description="")
    repo = PgKnowledge(pg_engine, kb.id)
    cluster = _sample_cluster(kb_id=kb.id)
    repo.save_topic_clusters([cluster])
    listed = repo.list_topic_clusters()
    assert len(listed) == 1
    assert listed[0].name == "尺码选择"
    assert repo.get_topic_cluster("t1") is not None
    repo.mark_topic_clusters_stale()
    assert repo.list_topic_clusters() == []
    assert repo.list_topic_clusters(status="stale")[0].id == "t1"


@pytest.mark.skipif(not pg_enabled(), reason="AKOS_USE_PG not enabled")
def test_pg_topic_cluster_kb_isolation(pg_engine, pg_kb_repo):
    from akos.adapters.persistence.pg_knowledge import PgKnowledge

    kb_a = pg_kb_repo.create(name="topic-kb-a", domain_type="ecommerce_cs", description="")
    kb_b = pg_kb_repo.create(name="topic-kb-b", domain_type="ecommerce_cs", description="")
    repo_a = PgKnowledge(pg_engine, kb_a.id)
    repo_b = PgKnowledge(pg_engine, kb_b.id)
    repo_a.save_topic_clusters([_sample_cluster(cluster_id="t-a", kb_id=kb_a.id)])
    repo_b.save_topic_clusters([_sample_cluster(cluster_id="t-b", kb_id=kb_b.id, name="退货政策")])
    assert len(repo_a.list_topic_clusters()) == 1
    assert len(repo_b.list_topic_clusters()) == 1
    assert repo_a.get_topic_cluster("t-b") is None
    assert repo_b.get_topic_cluster("t-a") is None
