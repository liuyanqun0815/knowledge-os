"""Backward-compatible shim — prefer ``akos.domain.ports.evolution``."""

from akos.domain.ports.evolution import ApplyReport, EvolutionPort, KnowledgeDiff

__all__ = ["ApplyReport", "EvolutionPort", "KnowledgeDiff"]
