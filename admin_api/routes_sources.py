"""Backward-compatible shim — prefer akos.interfaces.api.admin_api.routes_sources."""

from importlib import import_module
import sys

sys.modules[__name__] = import_module("akos.interfaces.api.admin_api.routes_sources")
