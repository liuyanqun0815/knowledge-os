"""Backward-compatible shim — prefer akos.application.evolution.service."""

from importlib import import_module
import sys

sys.modules[__name__] = import_module('akos.application.evolution.service')
