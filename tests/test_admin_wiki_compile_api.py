from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from akos.interfaces.api.main import create_app
from akos.bootstrap import DEFAULT_IN_MEMORY_KB_ID, build_orchestrator_for_kb
from akos.domain.models.knowledge import Claim, Source, SourceChunk
from akos.application.wiki.paths import compile_wiki_root


@pytest.fixture
def admin_client(tmp_path, monkeypatch):
    monkeypatch.delenv("ADMIN_API_TOKEN", raising=False)
    monkeypatch.setenv("AKOS_USE_PG", "false")
    monkeypatch.setenv("AKOS_TOPIC_CLUSTER", "true")
    monkeypatch.setenv("AKOS_WIKI_COMPILE", "true")
    monkeypatch.setenv("AKOS_WIKI_COMPILE_LLM", "false")
    return TestClient(create_app(data_root=str(tmp_path)))


def _cached_orchestrator(client: TestClient, kb_id: str):
    cache = client.app.state.orchestrator_cache
    if kb_id not in cache:
        cache[kb_id] = build_orchestrator_for_kb(kb_id)
    return cache[kb_id]


def _seed_compile_source(client: TestClient, kb_id: str = DEFAULT_IN_MEMORY_KB_ID) -> str:
    knowledge = _cached_orchestrator(client, kb_id).deps.knowledge
    source_id = "s-compile"
    knowledge.save_source(
        Source(
            id=source_id,
            title="退款政策",
            type="md",
            uri="file://s-compile",
            version="1",
            created_at=datetime(2026, 9, 14, tzinfo=timezone.utc),
            status="active",
        )
    )
    knowledge.save_chunks(
        source_id,
        [
            SourceChunk(
                id="c-compile",
                source_id=source_id,
                chunk_index=0,
                title="退款时效",
                summary=None,
                text="买家可在七天内申请退款。",
                start=0,
                end=14,
                topics=["退款政策"],
                status="active",
                created_at=datetime(2026, 9, 14, tzinfo=timezone.utc),
            )
        ],
    )
    knowledge.append_claim(
        Claim(
            id="cl-compile",
            family_id="f-compile",
            version=1,
            subject="退款",
            predicate="时效",
            object="7天",
            subject_type="Concept",
            object_type="Concept",
            confidence=0.9,
            status="active",
            valid_from=None,
            valid_to=None,
            source_ids=[source_id],
        )
    )
    return source_id


def _seed_stale_chunk(client: TestClient, kb_id: str = DEFAULT_IN_MEMORY_KB_ID) -> str:
    knowledge = _cached_orchestrator(client, kb_id).deps.knowledge
    source_id = "s-stale"
    knowledge.save_source(
        Source(
            id=source_id,
            title="旧文档",
            type="md",
            uri="file://s-stale",
            version="1",
            created_at=datetime(2026, 9, 14, tzinfo=timezone.utc),
            status="active",
        )
    )
    knowledge.save_chunks(
        source_id,
        [
            SourceChunk(
                id="c-stale",
                source_id=source_id,
                chunk_index=0,
                title="过期段",
                summary=None,
                text="将被清理的 stale 段落",
                start=0,
                end=12,
                topics=[],
                status="stale",
                created_at=datetime(2026, 9, 14, tzinfo=timezone.utc),
            )
        ],
    )
    return source_id


def test_admin_wiki_compile_writes_compile_layer(admin_client, tmp_path: Path):
    kb_id = DEFAULT_IN_MEMORY_KB_ID
    source_id = _seed_compile_source(admin_client, kb_id)
    rebuild = admin_client.post(f"/admin/knowledge-bases/{kb_id}/topics/rebuild")
    assert rebuild.status_code == 200, rebuild.text

    response = admin_client.post(
        f"/admin/knowledge-bases/{kb_id}/wiki/compile",
        params={"source_id": source_id},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["kb_id"] == kb_id
    assert body["pages_written"] >= 1
    assert "退款政策" in body["topics"]
    assert source_id in body["source_ids"]

    wiki_root = compile_wiki_root(tmp_path, kb_id)
    assert (wiki_root / "index.md").exists()
    # Default wiki_hierarchy: hub folders (`{hub}/_index.md`), not flat topic-*.md
    hub_indexes = list(wiki_root.glob("*/_index.md"))
    nested_md = [
        p
        for p in wiki_root.rglob("*.md")
        if p.name != "index.md" and ".meta" not in p.parts
    ]
    assert hub_indexes or nested_md, "expected hierarchical wiki pages under kb/{kb_id}/wiki"
    assert not list(wiki_root.glob("topic-*.md"))


def test_admin_wiki_compile_all_sources(admin_client, tmp_path: Path):
    kb_id = DEFAULT_IN_MEMORY_KB_ID
    _seed_compile_source(admin_client, kb_id)
    rebuild = admin_client.post(f"/admin/knowledge-bases/{kb_id}/topics/rebuild")
    assert rebuild.status_code == 200, rebuild.text

    response = admin_client.post(f"/admin/knowledge-bases/{kb_id}/wiki/compile")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["pages_written"] >= 1
    assert (compile_wiki_root(tmp_path, kb_id) / "index.md").exists()


def test_admin_purge_stale_chunks_kb_wide(admin_client):
    kb_id = DEFAULT_IN_MEMORY_KB_ID
    source_id = _seed_stale_chunk(admin_client, kb_id)
    knowledge = _cached_orchestrator(admin_client, kb_id).deps.knowledge
    assert len(knowledge.list_chunks(source_id, status="stale")) == 1

    response = admin_client.post(f"/admin/knowledge-bases/{kb_id}/chunks/purge-stale")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["kb_id"] == kb_id
    assert body["deleted"] == 1
    assert knowledge.list_chunks(source_id, status="stale") == []
    assert knowledge.get_chunk("c-stale") is None
