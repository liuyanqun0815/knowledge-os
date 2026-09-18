"""Backward-compatible shim — prefer ``akos.adapters.retrieval.wiki_keywords``."""

from akos.adapters.retrieval.wiki_keywords import extract_keywords

__all__ = ["extract_keywords"]
