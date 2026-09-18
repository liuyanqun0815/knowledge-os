"""Backward-compatible shim — prefer ``akos.adapters.retrieval.fusion``."""

from akos.adapters.retrieval.fusion import fuse_hits, normalize_hit_scores, route_fusion_weights, rrf_score

__all__ = ["fuse_hits", "normalize_hit_scores", "route_fusion_weights", "rrf_score"]
