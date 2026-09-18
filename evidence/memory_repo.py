"""Backward-compatible shim — prefer ``akos.adapters.persistence.evidence_memory``."""

from akos.adapters.persistence.evidence_memory import InMemoryEvidence

__all__ = ["InMemoryEvidence"]
