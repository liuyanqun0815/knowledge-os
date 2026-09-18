"""Backward-compatible shim — prefer akos.application.ask.synthesis."""

from importlib import import_module
import sys

sys.modules[__name__] = import_module('akos.application.ask.synthesis')
