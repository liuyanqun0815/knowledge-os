from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from tests.conftest import admin_upload_item

ROOT = Path(__file__).resolve().parents[1]
SAMPLE_MD = ROOT / "samples" / "refund_policy_v3.md"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.delenv("ADMIN_API_TOKEN", raising=False)
    monkeypatch.setenv("AKOS_USE_PG", "false")
    return TestClient(create_app(data_root=str(tmp_path / "data")))


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
    assert upload.status_code == 200

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
    assert response.status_code == 200
    payload = response.json()
    assert payload["upload_mode"] == "zip"
    assert payload["files_ingested"] == 2
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
    assert response.status_code == 200
    payload = response.json()
    assert payload["upload_mode"] == "zip"
    assert payload["files_ingested"] == 2
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
    assert upload.status_code == 200
    upload_body = upload.json()
    assert upload_body["upload_mode"] == "single"
    source_id = admin_upload_item(upload)["source_id"]

    claims = client.get(f"/admin/knowledge-bases/{kb_id}/sources/{source_id}/claims")
    assert claims.status_code == 200
    body = claims.json()
    assert len(body) >= 1
    assert body[0]["subject"]
    assert body[0]["predicate"]
    assert body[0]["object"]
