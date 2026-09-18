"""Backward-compatible shim — prefer ``akos.adapters.persistence.pg_evidence``."""

from akos.adapters.persistence.pg_evidence import PgEvidence

__all__ = ["PgEvidence"]
