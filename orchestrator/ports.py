"""Backward-compatible shim — prefer ``akos.domain.ports.orchestrator``."""

from akos.domain.ports.orchestrator import OrchestratorPort

__all__ = ["OrchestratorPort"]
