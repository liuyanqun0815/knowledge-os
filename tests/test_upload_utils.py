from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

from infra.upload_utils import (
    directory_from_relative,
    extract_zip_documents,
    fuzzy_match,
    source_id_from_relative_path,
)


def test_source_id_from_nested_path():
    assert source_id_from_relative_path(Path("policies/refund_v3.md")) == "policies__refund_v3"


def test_fuzzy_match_partial_path():
    assert fuzzy_match("refund", "policies__refund_v3", "refund_v3.md", "policies/refund_v3.md")
    assert not fuzzy_match("missing", "guide.md", "docs/guide.md")


def test_extract_zip_preserves_directories(tmp_path: Path):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("policies/refund.md", "# refund")
        archive.writestr("notes/readme.txt", "hello")
        archive.writestr("ignore.pdf", "binary")

    extracted, errors = extract_zip_documents(buffer.getvalue(), tmp_path)
    assert len(extracted) == 2
    assert (tmp_path / "policies" / "refund.md").exists()
    assert any("ignore.pdf" in error for error in errors)


def test_directory_from_relative():
    assert directory_from_relative(Path("policies/refund.md")) == "/policies"
    assert directory_from_relative(Path("root.md")) == "/"
