from __future__ import annotations

from datetime import datetime, timezone

import pytest

from akos.adapters.persistence.graph_memory import InMemoryGraph
from akos.adapters.persistence.pg_embeddings import PgEmbeddingStore
from akos.domain.models.knowledge import Claim
from akos.adapters.retrieval.embedder import HashEmbedder, claim_embedding_text
from akos.adapters.retrieval.hybrid import HybridRetrieval
from akos.domain.ports.retrieval import RetrievalMode


@pytest.fixture
def pg_embedding_store(pg_engine, pg_knowledge):
    kb_id = pg_knowledge._knowledge_base_id  # test-only access to fixture kb scope
    return PgEmbeddingStore(pg_engine, kb_id, dims=768)


def test_pg_embedding_store_search_claims(pg_knowledge, pg_embedding_store):
    kb_id = pg_knowledge._knowledge_base_id
    claim_id = f"c-embed-1-{kb_id[:8]}"
    embedder = HashEmbedder(dims=768)
    claim = Claim(
        id=claim_id,
        family_id=f"f1-{kb_id[:8]}",
        version=1,
        subject="投诉升级",
        predicate="包含",
        object="找主管、12315",
        subject_type="Concept",
        object_type="Concept",
        confidence=0.9,
        status="active",
        valid_from=datetime.now(timezone.utc),
        valid_to=None,
        source_ids=["s1"],
    )
    pg_knowledge.append_claim(claim)
    text = claim_embedding_text(claim.subject, claim.predicate, claim.object)
    pg_embedding_store.upsert("claim", claim.id, embedder.embed([text])[0])

    query_vec = embedder.embed(["投诉 找主管"])[0]
    hits = pg_embedding_store.search_claims(query_vec, top_k=5)

    assert hits
    assert hits[0].claim_id == claim_id


def test_hybrid_retrieval_uses_pg_vector_without_memory_vectors(pg_knowledge, pg_embedding_store):
    kb_id = pg_knowledge._knowledge_base_id
    claim_id = f"c-hybrid-pg-{kb_id[:8]}"
    graph = InMemoryGraph()
    embedder = HashEmbedder(dims=768)
    claim = Claim(
        id=claim_id,
        family_id=f"f2-{kb_id[:8]}",
        version=1,
        subject="节假日",
        predicate="覆盖",
        object="春节、国庆",
        subject_type="Policy",
        object_type="Concept",
        confidence=0.9,
        status="active",
        valid_from=datetime.now(timezone.utc),
        valid_to=None,
        source_ids=[],
    )
    pg_knowledge.append_claim(claim)
    retrieval = HybridRetrieval(
        pg_knowledge,
        graph,
        embedder=embedder,
        embedding_store=pg_embedding_store,
    )
    retrieval.index_claim(claim)

    assert retrieval.uses_pg_embeddings is True
    assert not retrieval._claim_vectors  # noqa: SLF001

    hits = retrieval.search("春节发货时效", RetrievalMode.VECTOR, {})
    assert hits
    assert hits[0].claim_id == claim_id
