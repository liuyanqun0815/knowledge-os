from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from akos.interfaces.api.main import create_app
from infra.bootstrap import DEFAULT_IN_MEMORY_KB_ID
from tests.conftest import ROOT, admin_upload_item, pg_enabled

SAMPLE_MD = ROOT / "samples" / "refund_policy_v3.md"


@pytest.fixture
def pg_admin_client(tmp_path, pg_engine, monkeypatch):
    monkeypatch.setenv("AKOS_USE_PG", "true")
    monkeypatch.delenv("ADMIN_API_TOKEN", raising=False)
    from infra.db import reset_engine
    from infra.settings import Settings, get_settings

    get_settings.cache_clear()
    reset_engine()
    app = create_app(data_root=str(tmp_path))
    app.state.settings = Settings(data_root=str(tmp_path), use_pg=True)
    return TestClient(app)


def test_create_kb_upload_list_sources_claims_in_memory(tmp_path, monkeypatch):
    monkeypatch.delenv("ADMIN_API_TOKEN", raising=False)
    app = create_app(data_root=str(tmp_path))
    client = TestClient(app)
    kb_id = DEFAULT_IN_MEMORY_KB_ID

    with SAMPLE_MD.open("rb") as handle:
        upload = client.post(
            f"/admin/knowledge-bases/{kb_id}/sources/upload",
            files={"file": ("refund_policy_v3.md", handle, "text/markdown")},
            data={"source_type": "policy"},
        )
    assert upload.status_code == 202, upload.text
    body = admin_upload_item(upload)
    assert body["claims_created"] == 0
    assert body["source_id"]
    assert upload.json()["accepted_async"] is True

    listed = client.get(f"/admin/knowledge-bases/{kb_id}/sources")
    assert listed.status_code == 200
    sources = listed.json()
    assert len(sources) >= 1
    assert any(item["id"] == body["source_id"] for item in sources)
    assert any(item["claims_count"] >= 1 for item in sources)
    assert Path(body["path"]).exists()


@pytest.mark.skipif(not pg_enabled(), reason="requires AKOS_USE_PG=true")
def test_admin_kb_crud_and_upload_flow(pg_admin_client):
    client = pg_admin_client

    created = client.post(
        "/admin/knowledge-bases",
        json={
            "name": "admin-api-test",
            "domain_type": "ecommerce_cs",
            "description": "task 7",
        },
    )
    assert created.status_code == 201, created.text
    kb = created.json()
    kb_id = kb["id"]
    assert kb["name"] == "admin-api-test"
    assert kb["status"] == "active"

    listed = client.get("/admin/knowledge-bases")
    assert listed.status_code == 200
    assert any(item["id"] == kb_id for item in listed.json())

    detail = client.get(f"/admin/knowledge-bases/{kb_id}")
    assert detail.status_code == 200
    assert detail.json()["domain_type"] == "ecommerce_cs"

    patched = client.patch(
        f"/admin/knowledge-bases/{kb_id}",
        json={"name": "admin-api-renamed", "description": "updated"},
    )
    assert patched.status_code == 200
    assert patched.json()["name"] == "admin-api-renamed"

    with SAMPLE_MD.open("rb") as handle:
        upload = client.post(
            f"/admin/knowledge-bases/{kb_id}/sources/upload",
            files={"file": ("refund_policy_v3.md", handle, "text/markdown")},
            data={"source_type": "policy"},
        )
    assert upload.status_code == 202, upload.text
    upload_body = admin_upload_item(upload)
    assert upload_body["claims_created"] == 0
    assert upload.json()["accepted_async"] is True

    sources = client.get(f"/admin/knowledge-bases/{kb_id}/sources")
    assert sources.status_code == 200
    assert len(sources.json()) >= 1
    assert any(item["claims_count"] >= 1 for item in sources.json())

    archived = client.patch(f"/admin/knowledge-bases/{kb_id}", json={"status": "archived"})
    assert archived.status_code == 200
    assert archived.json()["status"] == "archived"

    blocked = client.post(
        f"/admin/knowledge-bases/{kb_id}/sources/upload",
        files={"file": ("refund_policy_v3.md", SAMPLE_MD.read_bytes(), "text/markdown")},
    )
    assert blocked.status_code == 400


@pytest.mark.skipif(not pg_enabled(), reason="requires AKOS_USE_PG=true")
def test_admin_kb_crud_requires_pg(tmp_path, monkeypatch):
    monkeypatch.delenv("ADMIN_API_TOKEN", raising=False)
    app = create_app(data_root=str(tmp_path))
    client = TestClient(app)
    response = client.post(
        "/admin/knowledge-bases",
        json={"name": "no-pg", "domain_type": "ecommerce_cs"},
    )
    assert response.status_code == 503
