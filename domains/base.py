"""Backward-compatible shim — prefer ``akos.domain.ports.domain``."""

from __future__ import annotations

from akos.domain.ports.domain import DomainPort

__all__ = ["DomainPort"]
