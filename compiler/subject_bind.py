"""Backward-compatible shim — prefer akos.application.ingest.subject_bind."""

from importlib import import_module
import sys

sys.modules[__name__] = import_module('akos.application.ingest.subject_bind')
