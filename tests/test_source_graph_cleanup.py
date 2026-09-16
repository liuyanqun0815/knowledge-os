from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from admin_api.graph_helpers import build_snapshot
from admin_api.source_cleanup import purge_source_side_effects, sole_source_claims
from graph.memory_repo import InMemoryGraph
from infra.settings import Settings
from knowledge.memory_repo import InMemoryKnowledge
from knowledge.models import Source, SourceChunk
from knowledge.topic_service import rebuild_topic_clusters


def test_purge_source_side_effects_clears_topic_graph_snapshot():
    knowledge = InMemoryKnowledge()
    graph = InMemoryGraph()
    kb_id = "kb-graph-cleanup"
    knowledge.save_source(
        Source(
            id="s1",
            title="投诉流程",
            type="md",
            uri="file://s1",
            version="1",
            created_at=datetime(2026, 9, 14, tzinfo=timezone.utc),
            status="active",
        )
    )
    knowledge.save_chunks(
        "s1",
        [
            SourceChunk(
                id="chunk-1",
                source_id="s1",
                chunk_index=0,
                title="升级",
                summary=None,
                text="投诉升级找主管",
                start=0,
                end=10,
                topics=["投诉"],
                status="active",
                content_hash="hash-1",
                created_at=datetime(2026, 9, 14, tzinfo=timezone.utc),
            )
        ],
    )
    settings = Settings(_env_file=None, topic_cluster=True, topic_min_chunks=1)
    rebuild_topic_clusters(knowledge, graph, kb_id, settings)

    _, _, _, entity_total = build_snapshot(
        graph, entity_limit=200, edge_limit=500, knowledge=knowledge, active_only=True
    )
    assert entity_total > 0

    sole = sole_source_claims(knowledge, "s1")
    knowledge.delete_source("s1")
    deps = SimpleNamespace(
        knowledge=knowledge,
        graph=graph,
        knowledge_base_id=kb_id,
        chunk_retrieval=SimpleNamespace(remove_source=lambda _sid: None),
        retrieval=SimpleNamespace(remove_claim=lambda _cid: None),
    )
    purge_source_side_effects(deps, "s1", sole_claims=sole, settings=settings)

    entities, edges, _, entity_total = build_snapshot(
        graph, entity_limit=200, edge_limit=500, knowledge=knowledge, active_only=True
    )
    assert entity_total == 0
    assert entities == []
    assert edges == []
