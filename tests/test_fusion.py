from akos.adapters.retrieval.fusion import fuse_hits, normalize_hit_scores, route_fusion_weights
from akos.domain.ports.retrieval import Hit


def test_fuse_hits_prefers_both_channels():
    claim_hits = [Hit(score=1.0, snippet="claim", hit_type="claim", claim_id="c1")]
    chunk_hits = [Hit(score=0.9, snippet="chunk", hit_type="chunk", chunk_id="k1", source_id="s1")]
    fused = fuse_hits(claim_hits, chunk_hits, claim_weight=0.5)
    assert len(fused) == 2


def test_fuse_hits_scores_are_unit_interval_with_spread():
    claim_hits = [
        Hit(score=1.0, snippet="c1", hit_type="claim", claim_id="c1"),
        Hit(score=0.5, snippet="c2", hit_type="claim", claim_id="c2"),
    ]
    chunk_hits = [
        Hit(score=0.9, snippet="k1", hit_type="chunk", chunk_id="k1", source_id="s1"),
        Hit(score=0.2, snippet="k2", hit_type="chunk", chunk_id="k2", source_id="s1"),
    ]
    fused = fuse_hits(claim_hits, chunk_hits, claim_weight=1.0, chunk_weight=0.8)
    scores = [hit.score for hit in fused]
    assert min(scores) >= 0.0
    assert max(scores) <= 1.0
    assert max(scores) == 1.0
    assert max(scores) - min(scores) >= 0.5


def test_normalize_hit_scores_uses_rank_when_tied():
    hits = [
        Hit(score=0.015, snippet="a", hit_type="claim", claim_id="a"),
        Hit(score=0.015, snippet="b", hit_type="claim", claim_id="b"),
        Hit(score=0.015, snippet="c", hit_type="claim", claim_id="c"),
    ]
    normalized = normalize_hit_scores(hits)
    assert [hit.score for hit in normalized] == [1.0, round(2 / 3, 6), round(1 / 3, 6)]


def test_fuse_hits_prefers_strong_wiki_when_claim_chunk_weak():
    # claim 缺失、chunk 仅有弱通道时，强 wiki 命中应排在融合结果顶部（加权 RRF）
    claim_hits: list[Hit] = []
    chunk_hits = [Hit(score=0.1, snippet="weak chunk", hit_type="chunk", chunk_id="k1", source_id="s1")]
    wiki_hits = [
        Hit(
            score=1.0,
            snippet="退款政策主题页综述",
            hit_type="wiki",
            ref_id="topic-refund",
            title="退款政策",
            path="topic-退款政策.md",
        )
    ]
    fused = fuse_hits(
        claim_hits,
        chunk_hits,
        wiki_hits,
        claim_weight=1.0,
        wiki_weight=0.9,
        chunk_weight=0.8,
    )
    assert fused, "expected fused hits"
    assert fused[0].hit_type == "wiki"
    assert fused[0].ref_id == "topic-refund"
    assert fused[0].score == 1.0


def test_route_fusion_weights_for_explanatory_questions():
    assert route_fusion_weights("为什么节假日发货会延迟") == 0.3
    assert route_fusion_weights("七天无理由是什么") == 0.7
