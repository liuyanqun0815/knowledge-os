from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from akos.interfaces.api.main import create_app
from akos.application.evolution.family import family_key
from akos.bootstrap import DEFAULT_IN_MEMORY_KB_ID
from tests.conftest import admin_upload_item

ROOT = Path(__file__).resolve().parents[1]
V3 = ROOT / "samples" / "refund_policy_v3.md"
V4 = ROOT / "samples" / "refund_policy_v4.md"

FREIGHT_FAMILY_ID = family_key("七天无理由", "运费承担方", "Concept")


def _ingest_v3(client: TestClient, kb_id: str) -> str:
    response = client.post(
        "/sources",
        json={
            "knowledge_base_id": kb_id,
            "path": "samples/refund_policy_v3.md",
            "type": "policy",
        },
    )
    assert response.status_code == 200, response.text
    source_id = response.json()["source_id"]
    compile_response = client.post(f"/sources/{source_id}/compile", json={"knowledge_base_id": kb_id})
    assert compile_response.status_code == 200, compile_response.text
    return source_id


def test_upload_with_replaces_supersedes_freight_claim(tmp_path, monkeypatch):
    monkeypatch.delenv("ADMIN_API_TOKEN", raising=False)
    app = create_app(data_root=str(tmp_path))
    client = TestClient(app)
    kb_id = DEFAULT_IN_MEMORY_KB_ID

    with V3.open("rb") as handle:
        upload_v3 = client.post(
            f"/admin/knowledge-bases/{kb_id}/sources/upload",
            files={"file": ("refund_policy_v3.md", handle, "text/markdown")},
            data={"source_type": "policy"},
        )
    assert upload_v3.status_code == 202, upload_v3.text
    v3_source_id = admin_upload_item(upload_v3)["source_id"]

    with V4.open("rb") as handle:
        upload_v4 = client.post(
            f"/admin/knowledge-bases/{kb_id}/sources/upload",
            files={"file": ("refund_policy_v4.md", handle, "text/markdown")},
            data={"source_type": "policy", "replaces_source_id": v3_source_id},
        )
    assert upload_v4.status_code == 202, upload_v4.text

    history = client.get(
        f"/admin/knowledge-bases/{kb_id}/claims/{FREIGHT_FAMILY_ID}/history",
    )
    assert history.status_code == 200, history.text
    items = history.json()
    assert len(items) == 2
    assert items[0]["version"] == 1
    assert items[0]["object"] == "买家"
    assert items[0]["status"] == "superseded"
    assert items[1]["version"] == 2
    assert items[1]["object"] == "平台"
    assert items[1]["status"] == "active"


def test_register_compile_evolve_and_public_history(tmp_path):
    app = create_app(data_root=str(tmp_path))
    client = TestClient(app)
    kb_id = DEFAULT_IN_MEMORY_KB_ID

    v3_source_id = _ingest_v3(client, kb_id)

    register = client.post(
        "/sources",
        json={
            "knowledge_base_id": kb_id,
            "path": "samples/refund_policy_v4.md",
            "type": "policy",
            "replaces_source_id": v3_source_id,
        },
    )
    assert register.status_code == 200, register.text
    v4_source_id = register.json()["source_id"]

    compile_v4 = client.post(
        f"/sources/{v4_source_id}/compile",
        json={"knowledge_base_id": kb_id},
    )
    assert compile_v4.status_code == 200, compile_v4.text

    evolve = client.post(
        f"/admin/knowledge-bases/{kb_id}/sources/{v4_source_id}/evolve",
        json={},
    )
    assert evolve.status_code == 200, evolve.text
    report = evolve.json()
    assert report["source_old_id"] == v3_source_id
    assert report["source_new_id"] == v4_source_id
    assert len(report["claims_superseded"]) == 1
    assert len(report["claims_activated"]) == 1

    public_history = client.get(
        f"/claims/{FREIGHT_FAMILY_ID}/history",
        params={"knowledge_base_id": kb_id},
    )
    assert public_history.status_code == 200, public_history.text
    items = public_history.json()
    assert len(items) == 2
    assert items[-1]["object"] == "平台"
    assert items[-1]["status"] == "active"


def test_claim_history_requires_knowledge_base_id(tmp_path):
    app = create_app(data_root=str(tmp_path))
    client = TestClient(app)

    response = client.get(f"/claims/{FREIGHT_FAMILY_ID}/history")
    assert response.status_code == 422
