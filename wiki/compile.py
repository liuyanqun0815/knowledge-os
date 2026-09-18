"""Backward-compatible shim — prefer akos.application.wiki.compile."""

from importlib import import_module
import sys

sys.modules[__name__] = import_module('akos.application.wiki.compile')
