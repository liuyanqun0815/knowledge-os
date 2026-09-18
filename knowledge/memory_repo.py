"""Backward-compatible shim — prefer ``akos.adapters.persistence.knowledge_memory``."""

from akos.adapters.persistence.knowledge_memory import InMemoryKnowledge

__all__ = ["InMemoryKnowledge"]
