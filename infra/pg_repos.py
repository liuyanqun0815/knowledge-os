"""Backward-compatible shim — prefer ``akos.adapters.persistence.pg_knowledge``."""

from akos.adapters.persistence.pg_knowledge import PgKnowledge

__all__ = ["PgKnowledge"]
