"""Backward-compatible shim — prefer akos.application.ask.graphs.ask_graph."""

from importlib import import_module
import sys

sys.modules[__name__] = import_module('akos.application.ask.graphs.ask_graph')
