"""Backward-compatible shim — prefer ``akos.domain.ports.graph``."""

from akos.domain.ports.graph import Edge, GraphPort

__all__ = ["Edge", "GraphPort"]
