"""Backward-compatible shim — prefer ``akos.adapters.persistence.pg_memory``."""

from akos.adapters.persistence.pg_memory import PgMemory

__all__ = ["PgMemory"]
