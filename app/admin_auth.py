"""Backward-compatible shim — prefer akos.interfaces.api.admin_auth."""

from importlib import import_module
import sys

sys.modules[__name__] = import_module("akos.interfaces.api.admin_auth")
