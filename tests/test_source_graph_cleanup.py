from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from akos.interfaces.api.admin_api.graph_helpers import build_snapshot
from akos.interfaces.api.admin_api.source_cleanup import purge_source_side_effects, sole_source_claims
from akos.adapters.persistence.graph_memory import InMemoryGraph
from infra.settings import Settings
from akos.adapters.persistence.knowledge_memory import InMemoryKnowledge
from akos.domain.models.knowledge import Source, SourceChunk
from akos.application.topics.service import rebuild_topic_clusters


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


def test_purge_source_side_effects_removes_sole_claim_graph_edges():
    from akos.application.ingest.service import _entity_id
    from akos.domain.models.knowledge import Claim

    knowledge = InMemoryKnowledge()
    graph = InMemoryGraph()
    knowledge.save_source(
        Source(
            id="s1",
            title="政策",
            type="md",
            uri="file://s1",
            version="1",
            created_at=datetime(2026, 9, 14, tzinfo=timezone.utc),
            status="ready",
        )
    )
    claim = Claim(
        id="c1",
        family_id="f1",
        version=1,
        subject="七天无理由",
        predicate="运费承担方",
        object="买家",
        subject_type="RefundRule",
        object_type="Concept",
        confidence=0.9,
        status="active",
        valid_from=datetime(2026, 9, 14, tzinfo=timezone.utc),
        valid_to=None,
        source_ids=["s1"],
    )
    knowledge.append_claim(claim)
    src = _entity_id(claim.subject, claim.subject_type)
    dst = _entity_id(claim.object, claim.object_type)
    graph.upsert_entity(src, claim.subject_type, {"name": claim.subject})
    graph.upsert_entity(dst, claim.object_type, {"name": claim.object})
    graph.upsert_relation(src, claim.predicate, dst, {})

    sole = sole_source_claims(knowledge, "s1")
    knowledge.delete_source("s1")
    deps = SimpleNamespace(
        knowledge=knowledge,
        graph=graph,
        knowledge_base_id="kb-claim-cleanup",
        chunk_retrieval=SimpleNamespace(remove_source=lambda _sid: None),
        retrieval=SimpleNamespace(remove_claim=lambda _cid: None),
    )
    purge_source_side_effects(
        deps,
        "s1",
        sole_claims=sole,
        settings=Settings(_env_file=None, topic_cluster=False, wiki_compile=False),
    )

    assert graph.list_relations() == []
    assert graph.get_entity(src) is None
    assert graph.get_entity(dst) is None
