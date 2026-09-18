"""Backward-compatible shim — prefer ``akos.adapters.retrieval.embedder``."""

from akos.adapters.retrieval.embedder import (
    EmbedderPort,
    HashEmbedder,
    SentenceTransformerEmbedder,
    claim_embedding_text,
    configure_hf_hub,
    create_embedder,
    find_local_modelscope_snapshot,
    resolve_embedding_model_path,
    resolve_modelscope_model_dir,
)

__all__ = [
    "EmbedderPort",
    "HashEmbedder",
    "SentenceTransformerEmbedder",
    "claim_embedding_text",
    "configure_hf_hub",
    "create_embedder",
    "find_local_modelscope_snapshot",
    "resolve_embedding_model_path",
    "resolve_modelscope_model_dir",
]
