"""Phase 2.4 §8.4 acceptance: Docker ops + procedural memory + quarantine + admin debug."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from akos.interfaces.api.main import create_app
from akos.bootstrap import DEFAULT_IN_MEMORY_KB_ID, build_orchestrator_for_kb
from tests.conftest import admin_upload_item

ROOT = Path(__file__).resolve().parents[1]
SAMPLE_MD = ROOT / "samples" / "refund_policy_v3.md"


@pytest.fixture
def admin_client(tmp_path, monkeypatch):
    monkeypatch.delenv("ADMIN_API_TOKEN", raising=False)
    return TestClient(create_app(data_root=str(tmp_path)))


def _seed_kb(client: TestClient, kb_id: str = DEFAULT_IN_MEMORY_KB_ID) -> str:
    with SAMPLE_MD.open("rb") as handle:
        upload = client.post(
            f"/admin/knowledge-bases/{kb_id}/sources/upload",
            files={"file": ("refund_policy_v3.md", handle, "text/markdown")},
            data={"source_type": "policy"},
        )
    assert upload.status_code == 202, upload.text
    return admin_upload_item(upload)["source_id"]


def test_procedure_ask_returns_steps(seeded_kb_id):
    """§8.4.4: ask 流程问句 → procedure_id + steps in text."""
    orch = build_orchestrator_for_kb(seeded_kb_id)
    answer = orch.ask("仅退款流程怎么走？")

    assert answer.procedure_id == "proc-refund-only"
    assert "流程：仅退款流程" in answer.text
    assert "1. 校验签收状态" in answer.text
    assert "2. 判断原因码" in answer.text
    assert "3. 创建退款单" in answer.text


def test_quarantine_approve_creates_active_claim(admin_client):
    """§8.4.5: quarantine approve via admin API → active claim in main graph."""
    kb_id = DEFAULT_IN_MEMORY_KB_ID
    cache = admin_client.app.state.orchestrator_cache
    if kb_id not in cache:
        cache[kb_id] = build_orchestrator_for_kb(kb_id)
    knowledge = cache[kb_id].deps.knowledge
    knowledge.add_quarantine(
        "invalid_predicate",
        {
            "subject": "七天无理由",
            "predicate": "运费承担方",
            "object": "卖家",
            "subject_type": "RefundRule",
            "object_type": "Concept",
        },
    )

    listed = admin_client.get(f"/admin/knowledge-bases/{kb_id}/quarantine")
    assert listed.status_code == 200
    quarantine_id = listed.json()[0]["id"]

    approved = admin_client.post(f"/admin/knowledge-bases/{kb_id}/quarantine/{quarantine_id}/approve")
    assert approved.status_code == 200, approved.text
    claim = approved.json()["claim"]
    assert claim["status"] == "active"

    stored = knowledge.get_claim(claim["id"])
    assert stored is not None
    assert stored.status == "active"
    assert admin_client.get(f"/admin/knowledge-bases/{kb_id}/quarantine").json() == []


def test_admin_debug_ask_returns_trace(admin_client):
    """§8.4: POST debug/ask returns trace with retrieve/verify nodes."""
    kb_id = DEFAULT_IN_MEMORY_KB_ID
    _seed_kb(admin_client, kb_id)

    response = admin_client.post(
        f"/admin/knowledge-bases/{kb_id}/debug/ask",
        json={"question": "定制商品能否七天无理由退货？"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["text"]
    assert body["trace"]
    node_names = {entry["node"] for entry in body["trace"]}
    assert "retrieve" in node_names
    assert "verify" in node_names


def test_docker_compose_files_exist():
    """§8.4.1: docker compose config files ready."""
    assert (ROOT / "deploy" / "docker-compose.yml").is_file()
    assert (ROOT / "Dockerfile").is_file()
