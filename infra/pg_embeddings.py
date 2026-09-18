"""Backward-compatible shim — prefer ``akos.adapters.persistence.pg_embeddings``."""

from akos.adapters.persistence.pg_embeddings import PgEmbeddingStore

__all__ = ["PgEmbeddingStore"]
