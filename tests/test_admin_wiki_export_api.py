from __future__ import annotations

from fastapi.testclient import TestClient

from akos.interfaces.api.main import create_app
from infra.bootstrap import DEFAULT_IN_MEMORY_KB_ID
from tests.conftest import ROOT, admin_upload_item

SAMPLE_MD = ROOT / "samples" / "refund_policy_v3.md"


def test_admin_wiki_export_writes_default_path(tmp_path, monkeypatch):
    monkeypatch.delenv("ADMIN_API_TOKEN", raising=False)
    monkeypatch.setenv("AKOS_USE_PG", "false")
    monkeypatch.setenv("AKOS_EXTRACT_LLM", "false")
    monkeypatch.delenv("AKOS_LLM_API_KEY", raising=False)
    client = TestClient(create_app(data_root=str(tmp_path)))
    kb_id = DEFAULT_IN_MEMORY_KB_ID

    with SAMPLE_MD.open("rb") as handle:
        upload = client.post(
            f"/admin/knowledge-bases/{kb_id}/sources/upload",
            files={"file": ("refund_policy_v3.md", handle, "text/markdown")},
            data={"source_type": "policy"},
        )
    assert upload.status_code == 202, upload.text
    assert upload.json()["accepted_async"] is True
    assert admin_upload_item(upload)["claims_created"] == 0
    sources = client.get(f"/admin/knowledge-bases/{kb_id}/sources")
    assert any(item["claims_count"] >= 1 for item in sources.json())

    response = client.post(f"/admin/knowledge-bases/{kb_id}/wiki/export")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["kb_id"] == kb_id
    assert body["files_written"] >= 1
    assert body["source_pages"] >= 1
    assert (tmp_path / kb_id / "wiki" / "index.md").exists()


def test_admin_wiki_export_custom_relative_dir(tmp_path, monkeypatch):
    monkeypatch.delenv("ADMIN_API_TOKEN", raising=False)
    monkeypatch.setenv("AKOS_USE_PG", "false")
    monkeypatch.setenv("AKOS_EXTRACT_LLM", "false")
    monkeypatch.delenv("AKOS_LLM_API_KEY", raising=False)
    client = TestClient(create_app(data_root=str(tmp_path)))
    kb_id = DEFAULT_IN_MEMORY_KB_ID

    with SAMPLE_MD.open("rb") as handle:
        upload = client.post(
            f"/admin/knowledge-bases/{kb_id}/sources/upload",
            files={"file": ("refund_policy_v3.md", handle, "text/markdown")},
            data={"source_type": "policy"},
        )
    assert upload.status_code == 202, upload.text

    response = client.post(
        f"/admin/knowledge-bases/{kb_id}/wiki/export",
        json={"output_dir": f"{kb_id}/custom-wiki"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["files_written"] >= 1
    assert (tmp_path / kb_id / "custom-wiki" / "index.md").exists()
