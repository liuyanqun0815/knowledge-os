"""Backward-compatible shim — prefer ``akos.domain.ports.evidence``."""

from akos.domain.ports.evidence import EvidenceBundle, EvidencePort

__all__ = ["EvidenceBundle", "EvidencePort"]
