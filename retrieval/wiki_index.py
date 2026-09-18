"""Backward-compatible shim — prefer ``akos.adapters.retrieval.wiki_index``."""

from akos.adapters.retrieval.wiki_index import WikiPageRetrieval

__all__ = ["WikiPageRetrieval"]
