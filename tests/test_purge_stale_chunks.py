from datetime import datetime, timezone

from akos.application.ingest.chunk_service import index_source_chunks
from infra.settings import Settings
from akos.adapters.persistence.knowledge_memory import InMemoryKnowledge
from akos.domain.models.knowledge import Source, SourceChunk


def _source(sid: str = "s1") -> Source:
    return Source(
        id=sid,
        title="policy",
        type="policy",
        uri="file://p",
        version="1",
        created_at=datetime.now(timezone.utc),
        status="ready",
    )


def _chunk(chunk_id: str, source_id: str, index: int, text: str) -> SourceChunk:
    return SourceChunk(
        id=chunk_id,
        source_id=source_id,
        chunk_index=index,
        title=f"section-{index}",
        summary=None,
        text=text,
        start=0,
        end=len(text),
        section_path=[f"section-{index}"],
        topics=[],
        token_count=1,
        status="active",
        content_hash=text,
        created_at=datetime.now(timezone.utc),
    )


def test_reindex_fewer_chunks_purges_stale():
    knowledge = InMemoryKnowledge()
    knowledge.save_source(_source("s1"))
    knowledge.save_chunks(
        "s1",
        [
            _chunk("c0", "s1", 0, "first"),
            _chunk("c1", "s1", 1, "second"),
            _chunk("c2", "s1", 2, "third"),
        ],
    )

    knowledge.save_chunks("s1", [_chunk("c0b", "s1", 0, "only")])
    deleted = knowledge.purge_stale_chunks("s1")

    assert deleted == 3
    assert [c.id for c in knowledge.list_chunks("s1", status="active")] == ["c0b"]
    assert knowledge.list_chunks("s1", status="stale") == []
    assert knowledge.get_chunk("c0") is None
    assert knowledge.get_chunk("c1") is None
    assert knowledge.get_chunk("c2") is None


def test_index_source_chunks_purges_when_setting_enabled():
    knowledge = InMemoryKnowledge()
    knowledge.save_source(_source("s1"))
    knowledge.save_chunks(
        "s1",
        [
            _chunk("old0", "s1", 0, "first"),
            _chunk("old1", "s1", 1, "second"),
            _chunk("old2", "s1", 2, "third"),
        ],
    )
    knowledge.save_source_text("s1", "single reindexed body")
    settings = Settings(
        _env_file=None,
        ,
        chunk_max_chars=5000,
        chunk_max_per_doc=10,
        purge_stale_chunks=True,
    )

    report = index_source_chunks(knowledge, None, "s1", settings)
    assert report.chunks_created == 1

    active = knowledge.list_chunks("s1", status="active")
    assert len(active) == 1
    assert knowledge.list_chunks("s1", status="stale") == []
    assert knowledge.get_chunk("old0") is None
    assert knowledge.get_chunk("old1") is None
    assert knowledge.get_chunk("old2") is None


def test_index_source_chunks_keeps_stale_when_purge_disabled():
    knowledge = InMemoryKnowledge()
    knowledge.save_source(_source("s1"))
    knowledge.save_chunks(
        "s1",
        [
            _chunk("c0", "s1", 0, "first"),
            _chunk("c1", "s1", 1, "second"),
        ],
    )
    knowledge.save_source_text("s1", "only one block of text that stays as a single chunk")
    settings = Settings(
        _env_file=None,
        ,
        chunk_max_chars=5000,
        chunk_max_per_doc=10,
        purge_stale_chunks=False,
    )

    index_source_chunks(knowledge, None, "s1", settings)

    assert len(knowledge.list_chunks("s1", status="active")) == 1
    assert len(knowledge.list_chunks("s1", status="stale")) == 2
