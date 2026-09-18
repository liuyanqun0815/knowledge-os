"""Backward-compatible shim — prefer ``akos.adapters.persistence.graph_memory``."""

from akos.adapters.persistence.graph_memory import InMemoryGraph

__all__ = ["InMemoryGraph"]
