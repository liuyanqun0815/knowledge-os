from __future__ import annotations

from datetime import datetime, timezone

from graph.memory_repo import InMemoryGraph
from infra.settings import Settings
from knowledge.memory_repo import InMemoryKnowledge
from knowledge.models import Claim, Source, SourceChunk
from knowledge.topic_service import rebuild_topic_clusters, sync_graph_topics, topic_entity_id


def _source(source_id: str = "s1") -> Source:
    return Source(
        id=source_id,
        title="指南",
        type="md",
        uri=f"file://{source_id}",
        version="1",
        created_at=datetime(2026, 9, 11, tzinfo=timezone.utc),
        status="active",
    )


def _chunk(
    *,
    chunk_id: str = "c1",
    source_id: str = "s1",
    topics: list[str] | None = None,
    title: str | None = "尺码指南",
) -> SourceChunk:
    return SourceChunk(
        id=chunk_id,
        source_id=source_id,
        chunk_index=0,
        title=title,
        summary=None,
        text="示例文本",
        start=0,
        end=10,
        topics=topics or ["尺码选择"],
        status="active",
        created_at=datetime(2026, 9, 11, tzinfo=timezone.utc),
    )


def _claim(*, claim_id: str = "cl1", subject: str = "尺码选择", obj: str = "核对尺码表") -> Claim:
    return Claim(
        id=claim_id,
        family_id="f1",
        version=1,
        subject=subject,
        predicate="建议",
        object=obj,
        subject_type="Concept",
        object_type="Concept",
        confidence=0.9,
        status="active",
        valid_from=None,
        valid_to=None,
        source_ids=["s1"],
    )


def _seed_kb(knowledge: InMemoryKnowledge) -> None:
    knowledge.save_source(_source())
    knowledge.save_chunks("s1", [_chunk()])
    knowledge.append_claim(_claim())


def test_topic_entity_id_is_stable_and_prefixed():
    first = topic_entity_id("kb1", "尺码选择")
    second = topic_entity_id("kb1", "尺码选择")
    assert first == second
    assert first.startswith("topic:")
    assert len(first) == len("topic:") + 16


def test_rebuild_disabled_does_not_mutate():
    knowledge = InMemoryKnowledge()
    graph = InMemoryGraph()
    _seed_kb(knowledge)
    settings = Settings(topic_cluster=False)

    clusters = rebuild_topic_clusters(knowledge, graph, "kb1", settings)

    assert clusters == []
    assert knowledge.list_topic_clusters() == []
    assert graph.list_entities() == []


def test_rebuild_creates_clusters_and_topic_graph_nodes():
    knowledge = InMemoryKnowledge()
    graph = InMemoryGraph()
    _seed_kb(knowledge)
    settings = Settings(topic_cluster=True, topic_min_chunks=1, topic_graph_chunks=True)

    clusters = rebuild_topic_clusters(knowledge, graph, "kb1", settings)

    assert len(clusters) == 1
    saved = knowledge.list_topic_clusters()
    assert len(saved) == 1
    assert saved[0].chunk_ids == ["c1"]
    assert saved[0].claim_ids == ["cl1"]

    topic_entities = [(entity_id, props) for entity_id, props in graph.list_entities() if props.get("type") == "Topic"]
    assert len(topic_entities) == 1
    entity_id, props = topic_entities[0]
    assert entity_id == topic_entity_id("kb1", clusters[0].name)
    assert props["name"] == clusters[0].name
    assert props["kb_id"] == "kb1"

    cover_edges = [e for e in graph.relations if e.predicate == "涵盖"]
    assert cover_edges
    assert all(e.src == entity_id for e in cover_edges)

    chunk_edges = [e for e in graph.relations if e.predicate == "包含段落"]
    assert len(chunk_edges) == 1
    assert chunk_edges[0].src == entity_id
    assert chunk_edges[0].dst == "chunk:c1"
    chunk_entity = graph.get_entity("chunk:c1")
    assert chunk_entity is not None
    assert chunk_entity["type"] == "Chunk"


def test_sync_graph_topics_upserts_missing_concepts():
    graph = InMemoryGraph()
    knowledge = InMemoryKnowledge()
    _seed_kb(knowledge)
    settings = Settings()
    clusters = rebuild_topic_clusters(knowledge, graph, "kb1", settings)

    concept_entities = [props for _, props in graph.list_entities() if props.get("type") == "Concept"]
    names = {props["name"] for props in concept_entities}
    assert "尺码选择" in names
    assert "核对尺码表" in names

    topic_id = topic_entity_id("kb1", clusters[0].name)
    covered = {e.dst for e in graph.neighbors(topic_id, predicates=["涵盖"])}
    assert len(covered) >= 2


def test_rebuild_respects_topic_graph_chunks_false():
    knowledge = InMemoryKnowledge()
    graph = InMemoryGraph()
    _seed_kb(knowledge)
    settings = Settings(topic_graph_chunks=False)

    rebuild_topic_clusters(knowledge, graph, "kb1", settings)

    assert not any(props.get("type") == "Chunk" for _, props in graph.list_entities())
    assert not any(e.predicate == "包含段落" for e in graph.relations)


def test_rebuild_marks_previous_clusters_stale():
    knowledge = InMemoryKnowledge()
    graph = InMemoryGraph()
    _seed_kb(knowledge)
    settings = Settings()

    first = rebuild_topic_clusters(knowledge, graph, "kb1", settings)
    assert first
    first_id = first[0].id

    knowledge.mark_superseded("cl1")
    knowledge.save_chunks("s1", [_chunk(topics=["退货政策"])])
    knowledge.append_claim(_claim(claim_id="cl2", subject="退货政策", obj="七天无理由"))
    second = rebuild_topic_clusters(knowledge, graph, "kb1", settings)

    active = knowledge.list_topic_clusters(status="active")
    stale = knowledge.list_topic_clusters(status="stale")
    assert len(active) == 1
    assert active[0].id == second[0].id
    assert active[0].id != first_id
    assert any(c.id == first_id for c in stale)


def test_sync_graph_topics_links_existing_named_entities():
    from knowledge.models import TopicCluster

    graph = InMemoryGraph()
    graph.upsert_entity("e_existing", "RefundRule", {"name": "尺码选择"})
    cluster = TopicCluster(
        id="t1",
        knowledge_base_id="kb1",
        name="尺码选择",
        chunk_ids=["c1"],
        claim_ids=["cl1"],
        source_ids=["s1"],
        status="active",
        content_hash="h",
    )

    sync_graph_topics(
        graph,
        [cluster],
        claims=[_claim()],
        chunks=[_chunk()],
        graph_chunks=False,
    )

    topic_id = topic_entity_id("kb1", "尺码选择")
    edges = graph.neighbors(topic_id, predicates=["涵盖"])
    assert any(e.dst == "e_existing" for e in edges)
