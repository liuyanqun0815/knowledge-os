from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from akos.interfaces.api.main import create_app
from tests.conftest import admin_upload_item

ROOT = Path(__file__).resolve().parents[1]
SAMPLE_MD = ROOT / "samples" / "refund_policy_v3.md"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.delenv("ADMIN_API_TOKEN", raising=False)
    monkeypatch.setenv("AKOS_USE_PG", "false")
    return TestClient(create_app(data_root=str(tmp_path / "data")))


def test_upload_md_returns_202_accepted_async(client, tmp_path):
    kb_id = "async-md-kb"
    response = client.post(
        f"/admin/knowledge-bases/{kb_id}/sources/upload",
        files={"file": ("note.md", "# hi\n\n七天无理由适用类目为非定制商品。\n".encode(), "text/markdown")},
    )
    assert response.status_code == 202
    body = response.json()
    assert body["accepted_async"] is True
    assert body["results"][0]["claims_created"] == 0
    source_id = body["results"][0]["source_id"]

    sources = client.get(f"/admin/knowledge-bases/{kb_id}/sources")
    assert sources.status_code == 200
    statuses = {item["id"]: item["status"] for item in sources.json()}
    assert statuses[source_id] != "pending"


def test_upload_bad_suffix_returns_400(client):
    response = client.post(
        "/admin/knowledge-bases/bad-suffix-kb/sources/upload",
        files={"file": ("note.exe", b"not-a-doc", "application/octet-stream")},
    )
    assert response.status_code == 400
    assert "unsupported file type" in response.json()["detail"]


def test_upload_extract_failure_returns_202_then_failed(client, monkeypatch):
    from akos.interfaces.api.admin_api import upload_jobs
    from knowledge.errors import DomainError

    def boom(_path):
        raise DomainError("no extractable text")

    monkeypatch.setattr(upload_jobs, "materialize_markdown_for_ingest", boom)

    response = client.post(
        "/admin/knowledge-bases/extract-fail-kb/sources/upload",
        files={"file": ("empty.pdf", b"%PDF-1.4", "application/pdf")},
    )
    assert response.status_code == 202
    body = response.json()
    assert body["accepted_async"] is True
    source_id = body["results"][0]["source_id"]

    sources = client.get("/admin/knowledge-bases/extract-fail-kb/sources")
    assert sources.status_code == 200
    statuses = {item["id"]: item["status"] for item in sources.json()}
    assert statuses[source_id] == "failed"


def test_list_sources_supports_fuzzy_search(client, tmp_path):
    kb_id = "search-kb"
    kb_dir = tmp_path / "data" / kb_id
    kb_dir.mkdir(parents=True)
    target = kb_dir / "policies" / "refund_policy_v3.md"
    target.parent.mkdir(parents=True)
    target.write_text(SAMPLE_MD.read_text(encoding="utf-8"), encoding="utf-8")

    upload = client.post(
        f"/admin/knowledge-bases/{kb_id}/sources/upload",
        files={"file": ("refund_policy_v3.md", target.read_bytes(), "text/markdown")},
    )
    assert upload.status_code == 202

    matched = client.get(f"/admin/knowledge-bases/{kb_id}/sources", params={"q": "refund"})
    assert matched.status_code == 200
    body = matched.json()
    assert len(body) == 1
    assert body[0]["relative_path"] == "refund_policy_v3.md"
    assert body[0]["claims_count"] >= 1

    empty = client.get(f"/admin/knowledge-bases/{kb_id}/sources", params={"q": "not-found-term"})
    assert empty.status_code == 200
    assert empty.json() == []


def test_upload_zip_via_unified_endpoint(client, tmp_path):
    kb_id = "zip-unified-kb"
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("policies/refund_policy_v3.md", SAMPLE_MD.read_text(encoding="utf-8"))
        archive.writestr("notes/extra.txt", "七天无理由适用类目为非定制商品。")

    response = client.post(
        f"/admin/knowledge-bases/{kb_id}/sources/upload",
        files={"file": ("bundle.zip", buffer.getvalue(), "application/zip")},
    )
    assert response.status_code == 202
    payload = response.json()
    assert payload["upload_mode"] == "zip"
    assert payload["accepted_async"] is True
    assert payload["files_ingested"] == 0
    assert len(payload["results"]) == 2


def test_upload_zip_ingests_multiple_files(client, tmp_path):
    kb_id = "zip-kb"
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("policies/refund_policy_v3.md", SAMPLE_MD.read_text(encoding="utf-8"))
        archive.writestr("notes/extra.txt", "七天无理由适用类目为非定制商品。")

    response = client.post(
        f"/admin/knowledge-bases/{kb_id}/sources/upload-zip",
        files={"file": ("bundle.zip", buffer.getvalue(), "application/zip")},
    )
    assert response.status_code == 202
    payload = response.json()
    assert payload["upload_mode"] == "zip"
    assert payload["accepted_async"] is True
    assert payload["files_ingested"] == 0
    assert len(payload["results"]) == 2

    sources = client.get(f"/admin/knowledge-bases/{kb_id}/sources")
    assert sources.status_code == 200
    directories = {item["directory"] for item in sources.json()}
    assert "/policies" in directories
    assert "/notes" in directories


def test_list_source_claims(client, tmp_path):
    kb_id = "claims-kb"
    kb_dir = tmp_path / "data" / kb_id
    kb_dir.mkdir(parents=True)
    target = kb_dir / "refund_policy_v3.md"
    target.write_text(SAMPLE_MD.read_text(encoding="utf-8"), encoding="utf-8")

    upload = client.post(
        f"/admin/knowledge-bases/{kb_id}/sources/upload",
        files={"file": ("refund_policy_v3.md", target.read_bytes(), "text/markdown")},
    )
    assert upload.status_code == 202
    upload_body = upload.json()
    assert upload_body["upload_mode"] == "single"
    assert upload_body["accepted_async"] is True
    source_id = admin_upload_item(upload)["source_id"]

    claims = client.get(f"/admin/knowledge-bases/{kb_id}/sources/{source_id}/claims")
    assert claims.status_code == 200
    body = claims.json()
    assert len(body) >= 1
    assert body[0]["subject"]
    assert body[0]["predicate"]
    assert body[0]["object"]


def test_upload_docx_materializes_md_and_lists_source(client, tmp_path):
    pytest.importorskip("docx")
    from docx import Document

    kb_id = "docx-kb"
    buffer = io.BytesIO()
    document = Document()
    document.add_paragraph("七天无理由适用类目为非定制商品。")
    document.save(buffer)

    response = client.post(
        f"/admin/knowledge-bases/{kb_id}/sources/upload",
        files={
            "file": (
                "policy.docx",
                buffer.getvalue(),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert response.status_code == 202
    payload = response.json()
    assert payload["upload_mode"] == "single"
    assert payload["accepted_async"] is True
    assert payload["files_ingested"] == 0
    assert payload["results"][0]["relative_path"].endswith(".md")

    kb_dir = tmp_path / "data" / kb_id
    assert (kb_dir / "policy.docx").exists()
    assert (kb_dir / "policy.md").exists()

    sources = client.get(f"/admin/knowledge-bases/{kb_id}/sources")
    assert sources.status_code == 200
    assert any(item["relative_path"].endswith("policy.md") for item in sources.json())


def test_upload_pdf_text_layer_materializes_md(client, tmp_path):
    pytest.importorskip("fitz")
    import fitz

    kb_id = "pdf-kb"
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "七天无理由适用类目为非定制商品。")
    pdf_bytes = document.tobytes()
    document.close()

    response = client.post(
        f"/admin/knowledge-bases/{kb_id}/sources/upload",
        files={"file": ("guide.pdf", pdf_bytes, "application/pdf")},
    )
    assert response.status_code == 202
    payload = response.json()
    assert payload["accepted_async"] is True
    assert payload["files_ingested"] == 0
    assert (tmp_path / "data" / kb_id / "guide.pdf").exists()
    assert (tmp_path / "data" / kb_id / "guide.md").exists()
