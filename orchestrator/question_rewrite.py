"""Backward-compatible shim — prefer akos.application.ask.question_rewrite."""

from importlib import import_module
import sys

sys.modules[__name__] = import_module('akos.application.ask.question_rewrite')
