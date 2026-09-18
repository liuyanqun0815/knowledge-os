"""Backward-compatible shim — prefer ``akos.adapters.retrieval.chunk_index``."""

from akos.adapters.retrieval.chunk_index import ChunkRetrieval

__all__ = ["ChunkRetrieval"]
