from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from admin_api.schemas import ZipUploadItemResponse
from infra.doc_extract import EXTRACTABLE_UPLOAD_SUFFIXES
from infra.upload_utils import relative_path_from_kb_root, source_id_from_relative_path
from knowledge.models import Source

_LOG = logging.getLogger(__name__)


def ingest_path_for_upload(original: Path) -> Path:
    if original.suffix.lower() in EXTRACTABLE_UPLOAD_SUFFIXES:
        return original.with_suffix(".md")
    return original


def source_id_for_upload(kb_dir: Path, original: Path) -> str:
    ingest_path = ingest_path_for_upload(original)
    relative = relative_path_from_kb_root(ingest_path, kb_dir)
    return source_id_from_relative_path(relative)


def register_pending_source(
    *,
    knowledge,
    kb_dir: Path,
    original: Path,
    source_type: str,
    replaces_source_id: str | None = None,
) -> Source:
    source_id = source_id_for_upload(kb_dir, original)
    source = Source(
        id=source_id,
        title=ingest_path_for_upload(original).name,
        type=source_type,
        uri=f"file://{original.resolve()}",
        version="1",
        created_at=datetime.now(timezone.utc),
        status="pending",
        replaces_source_id=replaces_source_id,
    )
    return knowledge.save_source(source)


def pending_item_response(kb_dir: Path, original: Path, source_id: str) -> ZipUploadItemResponse:
    ingest_path = ingest_path_for_upload(original)
    try:
        rel = relative_path_from_kb_root(ingest_path, kb_dir)
        relative_path = rel.as_posix()
        directory = f"/{rel.parent.as_posix()}" if rel.parent.parts else "/"
    except ValueError:
        relative_path = ingest_path.name
        directory = "/"
    return ZipUploadItemResponse(
        source_id=source_id,
        path=str(ingest_path),
        claims_created=0,
        entities_upserted=0,
        evidence_links=0,
        quarantined=0,
        errors=[],
        relative_path=relative_path,
        directory=directory,
    )
