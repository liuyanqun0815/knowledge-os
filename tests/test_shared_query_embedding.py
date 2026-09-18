from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

from akos.adapters.persistence.knowledge_memory import InMemoryKnowledge
from knowledge.models import Claim, SourceChunk
from akos.adapters.persistence.graph_memory import InMemoryGraph
from akos.adapters.retrieval.chunk_index import ChunkRetrieval
from akos.adapters.retrieval.hybrid import HybridRetrieval
from akos.domain.ports.retrieval import RetrievalMode


def test_claim_and_chunk_reuse_shared_query_embedding_without_reembed():
    knowledge = InMemoryKnowledge()
    graph = InMemoryGraph()
    claim = Claim(
        id="c1",
        family_id="f1",
        version=1,
        subject="发货",
        predicate="时效",
        object="48小时",
        subject_type="Policy",
        object_type="Concept",
        confidence=0.9,
        status="active",
        valid_from=datetime.now(timezone.utc),
        valid_to=None,
        source_ids=["s1"],
    )
    knowledge.append_claim(claim)
    chunk = SourceChunk(
        id="ch1",
        source_id="s1",
        chunk_index=0,
        title="发货",
        summary="付款后48小时内发货",
        text="付款后48小时内发货",
        start=0,
        end=10,
        status="active",
        content_hash="h1",
        created_at=datetime.now(timezone.utc),
    )
    knowledge.save_chunks("s1", [chunk])

    embedder = MagicMock()
    embedder.embed.side_effect = AssertionError("should reuse shared query_embedding")
    claim_store = MagicMock()
    claim_store.search_claims.return_value = []
    chunk_store = MagicMock()
    chunk_store.search_chunks.return_value = []

    claim_retrieval = HybridRetrieval(knowledge, graph, embedder=embedder, embedding_store=claim_store)
    claim_retrieval.warm_index()
    chunk_retrieval = ChunkRetrieval(knowledge, embedder=embedder, embedding_store=chunk_store)

    shared = [0.25] * 8
    claim_retrieval.search("发货多久", RetrievalMode.VECTOR, {"query_embedding": shared, "top_k": 5})
    chunk_retrieval.search("发货多久", {"query_embedding": shared, "top_k": 5})

    claim_store.search_claims.assert_called_once()
    assert claim_store.search_claims.call_args.args[0] == shared
    chunk_store.search_chunks.assert_called_once()
    assert chunk_store.search_chunks.call_args.args[0] == shared
    embedder.embed.assert_not_called()
