from __future__ import annotations

from unittest.mock import MagicMock

from infra.settings import Settings
from orchestrator.nodes import rerank_node
from retrieval.ports import Hit
from retrieval.reranker import HashReranker


def test_rerank_node_skips_when_disabled(monkeypatch):
    monkeypatch.setattr(
        "orchestrator.nodes.get_settings",
        lambda: Settings(_env_file=None, rerank_enabled=False),
    )
    deps = MagicMock()
    deps.reranker = HashReranker()
    hits = [Hit(score=0.5, snippet="x", hit_type="chunk", chunk_id="c1")]

    out = rerank_node({"question": "发货多久", "hits": hits}, deps)

    assert out["hits"] == hits
    assert out["trace"][0]["node"] == "rerank"
    assert out["trace"][0]["status"] == "skipped"
    assert out["trace"][0]["detail"]["skipped_reason"] == "disabled"


def test_rerank_node_reorders_content_and_keeps_claims_first(monkeypatch):
    monkeypatch.setattr(
        "orchestrator.nodes.get_settings",
        lambda: Settings(
            _env_file=None,
            rerank_enabled=True,
            rerank_provider="hash",
            rerank_top_n=5,
            retrieval_top_k=5,
            rerank_min_score=0.0,
        ),
    )
    deps = MagicMock()
    deps.reranker = HashReranker()
    deps.knowledge = None
    hits = [
        Hit(score=0.2, snippet="无关段落", hit_type="chunk", chunk_id="c1"),
        Hit(score=0.9, snippet="发货时效48小时", hit_type="chunk", chunk_id="c2"),
        Hit(score=1.0, snippet="发货/时效/48小时", hit_type="claim", claim_id="cl1"),
    ]

    out = rerank_node({"question": "发货时效48小时", "hits": hits}, deps)

    assert out["hits"][0].claim_id == "cl1"
    assert out["hits"][0].hit_type == "claim"
    content = [hit for hit in out["hits"] if hit.hit_type == "chunk"]
    assert content[0].chunk_id == "c2"
    assert out["trace"][0]["node"] == "rerank"
    assert out["trace"][0]["status"] == "ok"
