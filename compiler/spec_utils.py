"""Backward-compatible shim — prefer akos.application.ingest.spec_utils."""

from importlib import import_module
import sys

sys.modules[__name__] = import_module('akos.application.ingest.spec_utils')
