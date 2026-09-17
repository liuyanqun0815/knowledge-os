"""Backward-compatible shim — prefer ``akos.domain.ports.verification``."""

from akos.domain.ports.verification import VerificationResult

__all__ = ["VerificationResult"]
