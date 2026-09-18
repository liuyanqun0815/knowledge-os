from __future__ import annotations

from datetime import datetime, timezone


def test_topic_cluster_settings_defaults(monkeypatch):
    monkeypatch.delenv("AKOS_TOPIC_CLUSTER", raising=False)
    monkeypatch.delenv("AKOS_TOPIC_MIN_CHUNKS", raising=False)
    monkeypatch.delenv("AKOS_TOPIC_GRAPH_CHUNKS", raising=False)
    monkeypatch.delenv("AKOS_TOPIC_LLM_SUMMARY", raising=False)
    monkeypatch.delenv("AKOS_TOPIC_CLAIM_BOOST", raising=False)
    from infra.settings import Settings

    s = Settings()
    assert s.topic_cluster is True
    assert s.topic_min_chunks == 1
    assert s.topic_graph_chunks is True
    assert s.topic_llm_summary is False
    assert s.topic_claim_boost == 0.1


def test_topic_cluster_dataclass():
    from akos.domain.models.knowledge import TopicCluster

    cluster = TopicCluster(
        id="t1",
        knowledge_base_id="kb1",
        name="尺码选择",
        aliases=["尺码表"],
        chunk_ids=["c1"],
        claim_ids=["cl1"],
        source_ids=["s1"],
        summary=None,
        status="active",
        content_hash="abc",
        updated_at=datetime(2026, 9, 11, tzinfo=timezone.utc),
    )
    assert cluster.name == "尺码选择"
    assert cluster.aliases == ["尺码表"]
