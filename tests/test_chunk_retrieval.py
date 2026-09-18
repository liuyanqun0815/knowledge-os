from datetime import datetime, timezone

from akos.adapters.persistence.knowledge_memory import InMemoryKnowledge
from knowledge.models import Source, SourceChunk
from akos.adapters.retrieval.chunk_index import ChunkRetrieval


def test_chunk_retrieval_finds_narrative_text():
    knowledge = InMemoryKnowledge()
    knowledge.save_source(
        Source("s1", "guide", "policy", "u", "1", datetime.now(timezone.utc), "ready")
    )
    chunk = SourceChunk(
        id="chunk-1",
        source_id="s1",
        chunk_index=0,
        title="发货说明",
        summary="节假日发货会顺延处理",
        text="如遇春节或国庆等长假，发货时效顺延至节后首个工作日。",
        start=0,
        end=30,
        section_path=["物流"],
        topics=["发货", "节假日"],
        token_count=10,
        status="active",
        content_hash="abc",
        created_at=datetime.now(timezone.utc),
    )
    knowledge.save_chunks("s1", [chunk])

    retrieval = ChunkRetrieval(knowledge)
    retrieval.index_chunks([chunk])
    hits = retrieval.search("节假日发货顺延", {})
    assert hits
    assert hits[0].chunk_id == "chunk-1"
    assert hits[0].hit_type == "chunk"
