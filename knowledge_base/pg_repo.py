"""Backward-compatible shim — prefer ``akos.adapters.persistence.kb_pg``."""

from akos.adapters.persistence.kb_pg import PgKnowledgeBaseRepo

__all__ = ["PgKnowledgeBaseRepo"]
