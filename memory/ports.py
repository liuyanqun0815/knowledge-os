"""Backward-compatible shim — prefer ``akos.domain.ports.memory``."""

from akos.domain.ports.memory import MemoryPort, RecallContext

__all__ = ["MemoryPort", "RecallContext"]
