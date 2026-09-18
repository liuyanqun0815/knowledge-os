"""Backward-compatible shim — prefer akos.application.ask.nodes."""

from importlib import import_module
import sys

sys.modules[__name__] = import_module('akos.application.ask.nodes')
