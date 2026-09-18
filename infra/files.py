"""Backward-compatible shim — prefer ``akos.adapters.files.local``."""

from akos.adapters.files.local import LocalFileStore, StoredFile

__all__ = ["LocalFileStore", "StoredFile"]
