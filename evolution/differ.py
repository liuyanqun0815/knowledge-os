"""Backward-compatible shim — prefer akos.application.evolution.differ."""

from importlib import import_module
import sys

sys.modules[__name__] = import_module('akos.application.evolution.differ')
