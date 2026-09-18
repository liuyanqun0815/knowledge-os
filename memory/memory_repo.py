"""Backward-compatible shim — prefer ``akos.adapters.persistence.memory_store``."""

from akos.adapters.persistence.memory_store import InMemoryMemoryStore

__all__ = ["InMemoryMemoryStore"]
