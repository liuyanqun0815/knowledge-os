from __future__ import annotations

import io
import zipfile
from pathlib import Path


def build_wiki_zip(wiki_root: Path, *, include_meta: bool = True) -> bytes:
    """Pack compiled wiki tree into an in-memory zip (relative paths preserved)."""
    root = Path(wiki_root)
    if not root.is_dir():
        raise FileNotFoundError(f"wiki_not_found: {root}")

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            relative = path.relative_to(root).as_posix()
            if relative.startswith(".meta/") and not include_meta:
                continue
            if path.suffix.lower() == ".md" or relative.startswith(".meta/"):
                archive.write(path, arcname=relative)
    return buffer.getvalue()
