from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from akos.adapters.persistence.evidence_memory import InMemoryEvidence
from akos.adapters.persistence.graph_memory import InMemoryGraph
from infra.settings import Settings
from akos.adapters.persistence.knowledge_memory import InMemoryKnowledge
from knowledge.models import Source, SourceChunk, TopicCluster
from akos.application.ingest.chunk_enrichment import enrich_chunks
from akos.application.wiki.export import export_wiki


def _chunk_enrich_llm(topics: list[str]):
    class Client:
        is_configured = True

        def chat_completions(self, messages, *, temperature=0.0, timeout=60.0):
            return json.dumps(
                {
                    'chunk_index': 0,
                    'title': '尺码指南',
                    'summary': '如何选择尺码',
                    'topics': topics,
                }
            )

    return Client()


def test_enrich_chunks_rebuilds_topic_clusters_when_enabled():
    knowledge = InMemoryKnowledge()
    graph = InMemoryGraph()
    knowledge.save_source(
        Source(
            id='s1',
            title='指南',
            type='md',
            uri='file://s1',
            version='1',
            created_at=datetime(2026, 9, 11, tzinfo=timezone.utc),
            status='active',
        )
    )
    knowledge.save_chunks(
        's1',
        [
            SourceChunk(
                id='c1',
                source_id='s1',
                chunk_index=0,
                title=None,
                summary=None,
                text='按身高体重选尺码',
                start=0,
                end=10,
                topics=[],
                status='active',
                created_at=datetime(2026, 9, 11, tzinfo=timezone.utc),
            )
        ],
    )
    indexed: list = []
    deps = SimpleNamespace(
        knowledge=knowledge,
        graph=graph,
        llm_client=_chunk_enrich_llm(['尺码选择']),
        chunk_retrieval=SimpleNamespace(index_chunks=lambda chunks: indexed.extend(chunks)),
    )
    settings = Settings(chunk_llm_enrich=True, topic_cluster=True, topic_min_chunks=1)

    enrich_chunks(kb_id='kb1', source_id='s1', deps=deps, settings=settings)

    clusters = knowledge.list_topic_clusters()
    assert len(clusters) >= 1
    assert clusters[0].name
    assert 'c1' in clusters[0].chunk_ids
    assert indexed


def test_enrich_chunks_skips_rebuild_when_topic_cluster_disabled():
    knowledge = InMemoryKnowledge()
    graph = InMemoryGraph()
    knowledge.save_source(
        Source(
            id='s1',
            title='指南',
            type='md',
            uri='file://s1',
            version='1',
            created_at=datetime(2026, 9, 11, tzinfo=timezone.utc),
            status='active',
        )
    )
    knowledge.save_chunks(
        's1',
        [
            SourceChunk(
                id='c1',
                source_id='s1',
                chunk_index=0,
                title=None,
                summary=None,
                text='按身高体重选尺码',
                start=0,
                end=10,
                topics=[],
                status='active',
                created_at=datetime(2026, 9, 11, tzinfo=timezone.utc),
            )
        ],
    )
    deps = SimpleNamespace(
        knowledge=knowledge,
        graph=graph,
        llm_client=_chunk_enrich_llm(['尺码选择']),
        chunk_retrieval=SimpleNamespace(index_chunks=lambda chunks: None),
    )
    settings = Settings(chunk_llm_enrich=True, topic_cluster=False)

    enrich_chunks(kb_id='kb1', source_id='s1', deps=deps, settings=settings)

    assert knowledge.list_topic_clusters() == []
    updated = knowledge.get_chunk('c1')
    assert updated is not None
    assert updated.topics == ['尺码选择']


def test_export_wiki_rebuilds_topics_when_empty(tmp_path: Path):
    knowledge = InMemoryKnowledge()
    evidence = InMemoryEvidence()
    graph = InMemoryGraph()
    knowledge.save_source(
        Source(
            id='s1',
            title='指南',
            type='md',
            uri='file://s1',
            version='1',
            created_at=datetime(2026, 9, 11, tzinfo=timezone.utc),
            status='active',
        )
    )
    knowledge.save_chunks(
        's1',
        [
            SourceChunk(
                id='c1',
                source_id='s1',
                chunk_index=0,
                title='尺码',
                summary=None,
                text='文本',
                start=0,
                end=4,
                topics=['尺码选择'],
                status='active',
                created_at=datetime(2026, 9, 11, tzinfo=timezone.utc),
            )
        ],
    )
    settings = Settings(topic_cluster=True, topic_min_chunks=1)
    assert knowledge.list_topic_clusters() == []

    export_wiki(
        knowledge,
        evidence,
        'kb1',
        tmp_path / 'wiki',
        settings=settings,
        graph=graph,
    )

    assert len(knowledge.list_topic_clusters()) >= 1


def test_export_wiki_rebuilds_topics_when_all_stale(tmp_path: Path):
    knowledge = InMemoryKnowledge()
    evidence = InMemoryEvidence()
    graph = InMemoryGraph()
    knowledge.save_source(
        Source(
            id='s1',
            title='指南',
            type='md',
            uri='file://s1',
            version='1',
            created_at=datetime(2026, 9, 11, tzinfo=timezone.utc),
            status='active',
        )
    )
    knowledge.save_chunks(
        's1',
        [
            SourceChunk(
                id='c1',
                source_id='s1',
                chunk_index=0,
                title='尺码',
                summary=None,
                text='文本',
                start=0,
                end=4,
                topics=['尺码选择'],
                status='active',
                created_at=datetime(2026, 9, 11, tzinfo=timezone.utc),
            )
        ],
    )
    knowledge.save_topic_clusters(
        [
            TopicCluster(
                id='old',
                knowledge_base_id='kb1',
                name='旧主题',
                chunk_ids=['c1'],
                claim_ids=[],
                source_ids=['s1'],
                status='stale',
                content_hash='x',
            )
        ]
    )
    settings = Settings(topic_cluster=True, topic_min_chunks=1)

    export_wiki(
        knowledge,
        evidence,
        'kb1',
        tmp_path / 'wiki',
        settings=settings,
        graph=graph,
    )

    active = knowledge.list_topic_clusters(status='active')
    assert len(active) >= 1
