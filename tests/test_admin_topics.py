from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from akos.interfaces.api.main import create_app
from akos.bootstrap import DEFAULT_IN_MEMORY_KB_ID, build_orchestrator_for_kb
from akos.domain.models.knowledge import Claim, Source, SourceChunk


@pytest.fixture
def admin_client(tmp_path, monkeypatch):
    monkeypatch.delenv("ADMIN_API_TOKEN", raising=False)
    monkeypatch.setenv("AKOS_USE_PG", "false")
    monkeypatch.setenv("AKOS_TOPIC_CLUSTER", "true")
    return TestClient(create_app(data_root=str(tmp_path)))


def _cached_orchestrator(client: TestClient, kb_id: str):
    cache = client.app.state.orchestrator_cache
    if kb_id not in cache:
        cache[kb_id] = build_orchestrator_for_kb(kb_id)
    return cache[kb_id]


def _seed_topic_source(client: TestClient, kb_id: str = DEFAULT_IN_MEMORY_KB_ID) -> None:
    knowledge = _cached_orchestrator(client, kb_id).deps.knowledge
    knowledge.save_source(
        Source(
            id="s-topic",
            title="尺码指南",
            type="md",
            uri="file://s-topic",
            version="1",
            created_at=datetime(2026, 9, 11, tzinfo=timezone.utc),
            status="active",
        )
    )
    knowledge.save_chunks(
        "s-topic",
        [
            SourceChunk(
                id="c-topic",
                source_id="s-topic",
                chunk_index=0,
                title="尺码选择",
                summary=None,
                text="请核对尺码表",
                start=0,
                end=10,
                topics=["尺码选择"],
                status="active",
                created_at=datetime(2026, 9, 11, tzinfo=timezone.utc),
            )
        ],
    )
    knowledge.append_claim(
        Claim(
            id="cl-topic",
            family_id="f-topic",
            version=1,
            subject="尺码选择",
            predicate="建议",
            object="核对尺码表",
            subject_type="Concept",
            object_type="Concept",
            confidence=0.9,
            status="active",
            valid_from=None,
            valid_to=None,
            source_ids=["s-topic"],
        )
    )


def test_admin_topics_rebuild_returns_cluster_counts(admin_client):
    kb_id = DEFAULT_IN_MEMORY_KB_ID
    _seed_topic_source(admin_client, kb_id)

    response = admin_client.post(f"/admin/knowledge-bases/{kb_id}/topics/rebuild")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["topics_created"] >= 1
    assert body["topics_updated"] == 0
    assert body["topics_stale"] == 0
    assert body["edges"] >= 1

    knowledge = _cached_orchestrator(admin_client, kb_id).deps.knowledge
    assert len(knowledge.list_topic_clusters(status="active")) >= 1


def test_admin_topics_rebuild_reports_updated_on_rerun(admin_client):
    kb_id = DEFAULT_IN_MEMORY_KB_ID
    _seed_topic_source(admin_client, kb_id)

    first = admin_client.post(f"/admin/knowledge-bases/{kb_id}/topics/rebuild")
    assert first.status_code == 200, first.text
    assert first.json()["topics_created"] >= 1

    second = admin_client.post(f"/admin/knowledge-bases/{kb_id}/topics/rebuild")
    assert second.status_code == 200, second.text
    body = second.json()
    assert body["topics_updated"] >= 1
    assert body["topics_created"] == 0
    assert body["topics_stale"] == 0
    assert body["edges"] >= 1


def test_admin_topics_rebuild_reports_stale_when_topic_replaced(admin_client):
    kb_id = DEFAULT_IN_MEMORY_KB_ID
    _seed_topic_source(admin_client, kb_id)

    first = admin_client.post(f"/admin/knowledge-bases/{kb_id}/topics/rebuild")
    assert first.status_code == 200, first.text

    knowledge = _cached_orchestrator(admin_client, kb_id).deps.knowledge
    knowledge.mark_superseded("cl-topic")
    knowledge.save_chunks(
        "s-topic",
        [
            SourceChunk(
                id="c-topic-2",
                source_id="s-topic",
                chunk_index=0,
                title="退货",
                summary=None,
                text="退货政策",
                start=0,
                end=10,
                topics=["退货政策"],
                status="active",
                created_at=datetime(2026, 9, 11, tzinfo=timezone.utc),
            )
        ],
    )
    knowledge.append_claim(
        Claim(
            id="cl-topic-2",
            family_id="f-topic-2",
            version=1,
            subject="退货政策",
            predicate="适用",
            object="七天无理由",
            subject_type="Concept",
            object_type="Concept",
            confidence=0.9,
            status="active",
            valid_from=None,
            valid_to=None,
            source_ids=["s-topic"],
        )
    )

    second = admin_client.post(f"/admin/knowledge-bases/{kb_id}/topics/rebuild")
    assert second.status_code == 200, second.text
    body = second.json()
    assert body["topics_created"] >= 1
    assert body["topics_stale"] >= 1
