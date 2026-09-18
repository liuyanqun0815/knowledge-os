"""Backward-compatible shim — prefer ``akos.adapters.retrieval.reranker``."""

from akos.adapters.retrieval.reranker import (
    BceCrossEncoderReranker,
    HashReranker,
    RerankerPort,
    _TransformersPairScorer,
    create_reranker,
    passage_for_hit,
    rerank_content_hits_preserving_claims,
    rerank_hits,
    resolve_rerank_model_path,
    to_unit_interval,
)

__all__ = [
    "BceCrossEncoderReranker",
    "HashReranker",
    "RerankerPort",
    "_TransformersPairScorer",
    "create_reranker",
    "passage_for_hit",
    "rerank_content_hits_preserving_claims",
    "rerank_hits",
    "resolve_rerank_model_path",
    "to_unit_interval",
]
