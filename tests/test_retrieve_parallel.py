from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock

from akos.application.ask.nodes import retrieve_node
from akos.domain.ports.retrieval import Hit, RetrievalMode


def test_retrieve_node_embeds_query_once_then_searches_in_parallel(monkeypatch):
    started: dict[str, float] = {}
    ended: dict[str, float] = {}
    embed_calls = {"n": 0}

    def _mark(name: str, delay: float, hits: list[Hit]):
        started[name] = time.perf_counter()
        time.sleep(delay)
        ended[name] = time.perf_counter()
        return hits

    claim_hits = [Hit(score=1.0, snippet="c", hit_type="claim", claim_id="c1")]
    chunk_hits = [Hit(score=0.9, snippet="k", hit_type="chunk", chunk_id="ch1")]
    wiki_hits = [Hit(score=0.8, snippet="w", hit_type="wiki", ref_id="p/a", path="p/a.md")]
    shared_vec = [0.1, 0.2, 0.3]

    def fake_retrieve(
        retrieval,
        question,
        mode,
        as_of=None,
        *,
        query_embedding=None,
        top_k=None,
        graph_top_k=None,
        graph_max_seeds=None,
        graph_per_seed=None,
    ):
        assert query_embedding == shared_vec
        return _mark("claim", 0.04, claim_hits)

    monkeypatch.setattr("akos.application.ask.nodes.retriever_agent.retrieve", fake_retrieve)

    chunk_retrieval = MagicMock()

    def fake_chunk_search(question, filters):
        assert filters.get("query_embedding") == shared_vec
        return _mark("chunk", 0.04, chunk_hits)

    chunk_retrieval.search.side_effect = fake_chunk_search
    chunk_retrieval._embedder = None

    wiki_retrieval = MagicMock()
    wiki_retrieval.search.side_effect = lambda *args, **kwargs: _mark("wiki", 0.04, wiki_hits)

    embedder = MagicMock()

    def fake_embed(texts):
        embed_calls["n"] += 1
        assert texts == ["发货多久？"]
        return [shared_vec]

    embedder.embed.side_effect = fake_embed

    settings = MagicMock(
        ,
        wiki_compile=True,
        retrieval_top_k=5,
        retrieval_graph_top_k=20,
        retrieval_graph_max_seeds=7,
        retrieval_graph_per_seed=4,
        chunk_min_score=0.0,
        retrieval_claim_weight=0.5,
        retrieval_wiki_weight=0.9,
        retrieval_chunk_weight=0.8,
        rerank_enabled=False,
    )
    monkeypatch.setattr("akos.application.ask.nodes.get_settings", lambda: settings)

    deps = MagicMock()
    deps.retrieval = MagicMock()
    deps.retrieval._embedder = embedder
    deps.chunk_retrieval = chunk_retrieval
    deps.wiki_retrieval = wiki_retrieval
    deps.reranker = None
    deps.knowledge = MagicMock()

    with ThreadPoolExecutor(max_workers=3) as pool:
        monkeypatch.setattr("akos.application.ask.nodes._RETRIEVE_POOL", pool)
        out = retrieve_node(
            {"question": "发货多久？", "retrieval_mode": RetrievalMode.HYBRID},
            deps,
        )

    assert embed_calls["n"] == 1
    assert set(started) == {"claim", "chunk", "wiki"}
    assert max(started.values()) < min(ended.values())
    detail = out["trace"][0]["detail"]
    assert detail["parallel"] is True
    assert detail["shared_query_embedding"] is True
    assert detail["embed_ms"] >= 0
    assert detail["claim_hits"] == 1
    assert detail["chunk_hits"] == 1
    assert detail["wiki_hits"] == 1
    assert out["trace"][0]["duration_ms"] < 200
