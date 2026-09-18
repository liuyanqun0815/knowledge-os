"""Backward-compatible shim — prefer akos.application.ingest.chunk_segmentation."""

from importlib import import_module
import sys

sys.modules[__name__] = import_module('akos.application.ingest.chunk_segmentation')
