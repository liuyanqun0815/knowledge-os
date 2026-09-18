"""Backward-compatible shim — prefer ``akos.adapters.persistence.pg_graph``."""

from akos.adapters.persistence.pg_graph import PgGraph

__all__ = ["PgGraph"]
