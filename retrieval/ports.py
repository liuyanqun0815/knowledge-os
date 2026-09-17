"""Backward-compatible shim — prefer ``akos.domain.ports.retrieval``."""

from akos.domain.ports.retrieval import Hit, RetrievalMode, RetrievalPort

__all__ = ["Hit", "RetrievalMode", "RetrievalPort"]
