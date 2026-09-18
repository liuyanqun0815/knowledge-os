from akos.adapters.retrieval.reranker import HashReranker, passage_for_hit, rerank_hits
from akos.domain.ports.retrieval import Hit
from infra.settings import Settings


def test_hash_reranker_prefers_matching_passage():
    reranker = HashReranker()
    scores = reranker.score_pairs(
        [
            ("客服禁用语", "禁止使用：不知道、不归我管"),
            ("客服禁用语", "投诉升级流程说明"),
        ]
    )
    assert scores[0] > scores[1]


def test_rerank_hits_reorders_fused_candidates():
    settings = Settings(_env_file=None, rerank_enabled=True, rerank_provider="hash", rerank_top_n=5, retrieval_top_k=2)
    reranker = HashReranker()
    hits = [
        Hit(score=0.9, snippet="投诉升级流程", hit_type="chunk", chunk_id="c1", source_id="s1"),
        Hit(score=0.8, snippet="客服禁用语：不知道、不归我管", hit_type="chunk", chunk_id="c2", source_id="s1"),
    ]
    reranked = rerank_hits("客服禁用语有哪些", hits, reranker, settings)
    assert len(reranked) == 2
    assert reranked[0].chunk_id == "c2"
    assert reranked[0].score >= reranked[1].score


def test_rerank_content_hits_preserves_claims_first():
    from akos.adapters.retrieval.reranker import rerank_content_hits_preserving_claims

    settings = Settings(_env_file=None, rerank_enabled=True, rerank_provider="hash", rerank_top_n=5, retrieval_top_k=2)
    reranker = HashReranker()
    hits = [
        Hit(score=0.95, snippet="投诉升级包含找主管", hit_type="claim", claim_id="cl1"),
        Hit(score=0.9, snippet="投诉升级流程", hit_type="chunk", chunk_id="c1", source_id="s1"),
        Hit(score=0.8, snippet="客服禁用语：不知道、不归我管", hit_type="chunk", chunk_id="c2", source_id="s1"),
        Hit(score=0.7, snippet="客服话术主题页", hit_type="wiki", ref_id="客服/话术", path="客服/话术.md"),
    ]
    merged = rerank_content_hits_preserving_claims(
        "客服禁用语有哪些",
        hits,
        reranker,
        settings,
    )
    assert merged[0].claim_id == "cl1"
    assert merged[0].hit_type == "claim"
    content = [hit for hit in merged if hit.hit_type in {"chunk", "wiki"}]
    assert content
    assert content[0].chunk_id == "c2"
    assert all(hit.hit_type == "claim" for hit in merged if hit.claim_id == "cl1")
    assert [hit.claim_id for hit in merged if hit.hit_type == "claim"] == ["cl1"]
    assert all(0.0 <= hit.score <= 1.0 for hit in merged)
    assert max(hit.score for hit in merged) == 1.0


def test_to_unit_interval_applies_sigmoid_for_logits():
    from akos.adapters.retrieval.reranker import to_unit_interval

    scores = to_unit_interval([2.0, 0.0, -2.0])
    assert all(0.0 < s < 1.0 for s in scores)
    assert scores[0] > scores[1] > scores[2]
    assert to_unit_interval([0.2, 0.8]) == [0.2, 0.8]


def test_rerank_hits_respects_min_score_threshold():
    settings = Settings(
        _env_file=None,
        rerank_enabled=True,
        rerank_provider="hash",
        rerank_top_n=5,
        rerank_min_score=0.9,
        retrieval_top_k=8,
    )
    reranker = HashReranker()
    hits = [
        Hit(score=0.5, snippet="完全无关的内容", hit_type="wiki", ref_id="w1"),
        Hit(score=0.4, snippet="另一段无关文本", hit_type="claim", claim_id="cl1"),
    ]
    reranked = rerank_hits("节假日发货", hits, reranker, settings)
    assert [hit.ref_id or hit.claim_id for hit in reranked] == ["w1", "cl1"]
    assert all(0.0 <= hit.score <= 1.0 for hit in reranked)


def test_passage_for_hit_uses_claim_triple():
    from datetime import datetime, timezone

    from akos.adapters.persistence.knowledge_memory import InMemoryKnowledge
    from knowledge.models import Claim

    knowledge = InMemoryKnowledge()
    claim = Claim(
        id="c1",
        family_id="f1",
        version=1,
        subject="投诉升级",
        predicate="包含",
        object="找主管",
        subject_type="Concept",
        object_type="Concept",
        confidence=0.9,
        status="active",
        valid_from=datetime(2026, 9, 11, tzinfo=timezone.utc),
        valid_to=None,
        source_ids=[],
    )
    knowledge.append_claim(claim)
    hit = Hit(score=1.0, snippet="短摘要", hit_type="claim", claim_id="c1")
    assert passage_for_hit(hit, knowledge) == "投诉升级 包含 找主管"


def test_passage_for_hit_prefers_chunk_title_and_summary():
    from akos.adapters.persistence.knowledge_memory import InMemoryKnowledge
    from knowledge.models import SourceChunk

    knowledge = InMemoryKnowledge()
    chunk = SourceChunk(
        id="ch1",
        source_id="s1",
        chunk_index=0,
        title="不予退换货情形",
        summary="定制商品不适用七天无理由退货。",
        text="这是很长的正文，不应进入 rerank passage。" + ("多余" * 80),
        start=0,
        end=10,
        status="active",
    )
    knowledge.save_chunks("s1", [chunk])
    hit = Hit(score=1.0, snippet="snippet", hit_type="chunk", chunk_id="ch1", source_id="s1")
    passage = passage_for_hit(hit, knowledge)
    assert passage == "不予退换货情形 定制商品不适用七天无理由退货。"
    assert "很长的正文" not in passage
    assert "多余" not in passage


def test_create_reranker_soft_fails_when_bce_load_breaks(monkeypatch):
    from akos.adapters.retrieval import reranker as reranker_mod

    settings = Settings(
        _env_file=None,
        rerank_enabled=True,
        rerank_provider="bce",
        rerank_model="./missing-rerank-model",
        rerank_model_source="local",
    )

    def _boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(reranker_mod, "BceCrossEncoderReranker", _boom)
    assert reranker_mod.create_reranker(settings) is None


def test_bce_reranker_falls_back_to_transformers(monkeypatch, tmp_path):
    import sys
    from types import SimpleNamespace

    from akos.adapters.retrieval import reranker as reranker_mod

    model_dir = tmp_path / "rerank"
    model_dir.mkdir()

    class FakeCrossEncoder:
        def __init__(self, *args, **kwargs):
            raise ValueError("Unrecognized processing class")

    class FakeFallback:
        def __init__(self, model_path, *, device="cpu", max_length=512):
            self.model_path = model_path

        def predict(self, pairs):
            return [0.9 for _ in pairs]

    monkeypatch.setitem(sys.modules, "sentence_transformers", SimpleNamespace(CrossEncoder=FakeCrossEncoder))
    monkeypatch.setattr(reranker_mod, "_TransformersPairScorer", FakeFallback)

    reranker = reranker_mod.BceCrossEncoderReranker(str(model_dir), device="cpu", max_length=64)
    assert reranker.score_pairs([("q", "p")]) == [0.9]
