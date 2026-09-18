from __future__ import annotations

from pathlib import Path


def compile_wiki_root(data_root: str | Path, kb_id: str) -> Path:
    """Return the compiled wiki root: ``{data_root}/kb/{kb_id}/wiki``."""
    return Path(data_root) / "kb" / kb_id / "wiki"
