"""Backward-compatible shim — prefer akos.interfaces.cli.main."""

from importlib import import_module
import sys

sys.modules[__name__] = import_module("akos.interfaces.cli.main")
