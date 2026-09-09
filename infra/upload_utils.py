from __future__ import annotations

import io
import zipfile
from pathlib import Path, PurePosixPath

ALLOWED_UPLOAD_SUFFIXES = {".md", ".txt"}


def source_id_from_relative_path(relative_path: Path) -> str:
    rel = relative_path.as_posix()
    without_suffix = PurePosixPath(rel).with_suffix("")
    parts = without_suffix.parts
    if not parts:
        return relative_path.stem
    return "__".join(parts)


def relative_path_from_kb_root(file_path: Path, kb_root: Path) -> Path:
    return file_path.resolve().relative_to(kb_root.resolve())


def directory_from_relative(relative_path: Path) -> str:
    parent = relative_path.parent
    if str(parent) in {"", "."}:
        return "/"
    return f"/{parent.as_posix()}"


def fuzzy_match(query: str, *fields: str) -> bool:
    needle = query.strip().lower()
    if not needle:
        return True
    haystack = " ".join(field for field in fields if field).lower()
    return needle in haystack


def extract_zip_documents(zip_bytes: bytes, kb_dir: Path) -> tuple[list[Path], list[str]]:
    extracted: list[Path] = []
    errors: list[str] = []
    kb_dir.mkdir(parents=True, exist_ok=True)
    kb_resolved = kb_dir.resolve()

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            member_path = PurePosixPath(info.filename)
            if member_path.name.startswith(".") or "__MACOSX" in member_path.parts:
                continue
            suffix = member_path.suffix.lower()
            if suffix not in ALLOWED_UPLOAD_SUFFIXES:
                errors.append(f"skipped unsupported file: {member_path.as_posix()}")
                continue
            target = (kb_dir / Path(*member_path.parts)).resolve()
            if not str(target).startswith(str(kb_resolved)):
                errors.append(f"skipped unsafe path: {member_path.as_posix()}")
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(info))
            extracted.append(target)

    return extracted, errors
