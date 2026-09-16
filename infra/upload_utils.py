from __future__ import annotations

import io
import zipfile
from pathlib import Path, PurePosixPath

from infra.doc_extract import ALLOWED_UPLOAD_SUFFIXES, EXTRACTABLE_UPLOAD_SUFFIXES, TEXT_UPLOAD_SUFFIXES

__all__ = [
    "ALLOWED_UPLOAD_SUFFIXES",
    "EXTRACTABLE_UPLOAD_SUFFIXES",
    "TEXT_UPLOAD_SUFFIXES",
    "safe_target_under_kb",
    "source_id_from_relative_path",
    "relative_path_from_kb_root",
    "directory_from_relative",
    "fuzzy_match",
    "extract_zip_documents",
]


def safe_target_under_kb(kb_dir: Path, relative_path: str) -> Path:
    normalized = relative_path.replace("\\", "/").strip()
    posix_path = PurePosixPath(normalized)
    if (
        not normalized
        or posix_path.is_absolute()
        or any(part in {"", ".", ".."} for part in posix_path.parts)
        or any(":" in part for part in posix_path.parts)
    ):
        raise ValueError(f"unsafe relative path: {relative_path}")

    kb_resolved = kb_dir.resolve()
    target = (kb_resolved / Path(*posix_path.parts)).resolve()
    if not target.is_relative_to(kb_resolved) or target == kb_resolved:
        raise ValueError(f"unsafe relative path: {relative_path}")
    return target


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
            try:
                target = safe_target_under_kb(kb_dir, member_path.as_posix())
            except ValueError:
                errors.append(f"skipped unsafe path: {member_path.as_posix()}")
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(info))
            extracted.append(target)

    return extracted, errors
