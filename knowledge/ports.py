"""Backward-compatible shim — prefer ``akos.domain.ports.knowledge``."""

from akos.domain.ports.knowledge import KnowledgePort

__all__ = ["KnowledgePort"]
