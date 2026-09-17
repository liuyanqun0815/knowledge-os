"""Backward-compatible shim — prefer ``akos.domain.ports.knowledge_base``."""

from akos.domain.ports.knowledge_base import KnowledgeBasePort

__all__ = ["KnowledgeBasePort"]
