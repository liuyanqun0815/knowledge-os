from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from infra.doc_extract import (
    ALLOWED_UPLOAD_SUFFIXES,
    extract_document,
    materialize_markdown_for_ingest,
)
from akos.domain.errors import DomainError

pytest.importorskip("docx")
pytest.importorskip("fitz")


def _write_docx(path: Path, paragraphs: list[str]) -> None:
    from docx import Document

    document = Document()
    for text in paragraphs:
        document.add_paragraph(text)
    document.save(str(path))


def _write_text_pdf(path: Path, text: str) -> None:
    import fitz

    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), text)
    document.save(str(path))
    document.close()


def test_allowed_suffixes_include_office_and_pdf():
    assert {".md", ".txt", ".pdf", ".docx"} <= ALLOWED_UPLOAD_SUFFIXES
    assert ".doc" not in ALLOWED_UPLOAD_SUFFIXES


def test_extract_docx_paragraphs(tmp_path: Path):
    path = tmp_path / "policy.docx"
    _write_docx(path, ["退款须知", "七日内可退"])
    text = extract_document(path)
    assert "退款须知" in text
    assert "七日内可退" in text


def test_extract_pdf_text_layer(tmp_path: Path):
    path = tmp_path / "guide.pdf"
    _write_text_pdf(path, "Hello PDF Layer")
    text = extract_document(path)
    assert "Hello PDF Layer" in text


def test_pdf_empty_layer_uses_ocr(tmp_path: Path):
    import fitz

    path = tmp_path / "scan.pdf"
    document = fitz.open()
    document.new_page()
    document.save(str(path))
    document.close()

    with patch("infra.doc_extract._ocr_pdf_page", return_value="OCR 扫描文字"):
        text = extract_document(path)
    assert "OCR 扫描文字" in text


def test_materialize_writes_sibling_md(tmp_path: Path):
    path = tmp_path / "policy.docx"
    _write_docx(path, ["条款 A"])
    md_path = materialize_markdown_for_ingest(path)
    assert md_path == path.with_suffix(".md")
    assert md_path.read_text(encoding="utf-8").strip() == "条款 A"
    assert path.exists()


def test_legacy_doc_is_unsupported(tmp_path: Path):
    path = tmp_path / "legacy.doc"
    path.write_bytes(b"not-a-real-doc")
    with pytest.raises(DomainError, match="unsupported"):
        extract_document(path)
    with pytest.raises(DomainError, match="unsupported"):
        materialize_markdown_for_ingest(path)


def test_unsupported_suffix_raises(tmp_path: Path):
    path = tmp_path / "note.rtf"
    path.write_text("x", encoding="utf-8")
    with pytest.raises(DomainError, match="unsupported"):
        materialize_markdown_for_ingest(path)
