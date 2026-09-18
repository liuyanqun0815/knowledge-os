"""Backward-compatible shim — prefer akos.application.wiki.archive."""

from importlib import import_module
import sys

sys.modules[__name__] = import_module('akos.application.wiki.archive')
