from retrieval.fusion import fuse_hits, route_fusion_weights
from retrieval.ports import Hit


def test_fuse_hits_prefers_both_channels():
    claim_hits = [Hit(score=1.0, snippet="claim", hit_type="claim", claim_id="c1")]
    chunk_hits = [Hit(score=0.9, snippet="chunk", hit_type="chunk", chunk_id="k1", source_id="s1")]
    fused = fuse_hits(claim_hits, chunk_hits, claim_weight=0.5)
    assert len(fused) == 2


def test_route_fusion_weights_for_explanatory_questions():
    assert route_fusion_weights("为什么节假日发货会延迟") == 0.3
    assert route_fusion_weights("七天无理由是什么") == 0.7
