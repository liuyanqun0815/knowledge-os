from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from compiler.service import _entity_id
from infra.bootstrap import DEFAULT_IN_MEMORY_KB_ID, build_orchestrator_for_kb
from knowledge.models import Claim, Source
from tests.conftest import admin_upload_item

ROOT = Path(__file__).resolve().parents[1]
SAMPLE_MD = ROOT / "samples" / "refund_policy_v3.md"


@pytest.fixture
def admin_client(tmp_path, monkeypatch):
    monkeypatch.delenv("ADMIN_API_TOKEN", raising=False)
    return TestClient(create_app(data_root=str(tmp_path)))


def _cached_orchestrator(client: TestClient, kb_id: str):
    cache = client.app.state.orchestrator_cache
    if kb_id not in cache:
        cache[kb_id] = build_orchestrator_for_kb(kb_id)
    return cache[kb_id]


def _seed_kb(client: TestClient, kb_id: str = DEFAULT_IN_MEMORY_KB_ID) -> str:
    with SAMPLE_MD.open("rb") as handle:
        upload = client.post(
            f"/admin/knowledge-bases/{kb_id}/sources/upload",
            files={"file": ("refund_policy_v3.md", handle, "text/markdown")},
            data={"source_type": "policy"},
        )
    assert upload.status_code == 200, upload.text
    return admin_upload_item(upload)["source_id"]


def test_list_quarantine_returns_id(admin_client):
    kb_id = DEFAULT_IN_MEMORY_KB_ID
    orch = _cached_orchestrator(admin_client, kb_id)
    orch.deps.knowledge.add_quarantine(
        "invalid_predicate",
        {
            "subject": "测试主体",
            "predicate": "无效谓词",
            "object": "测试客体",
            "subject_type": "Concept",
            "object_type": "Concept",
        },
    )

    response = admin_client.get(f"/admin/knowledge-bases/{kb_id}/quarantine")
    assert response.status_code == 200
    items = response.json()
    assert len(items) == 1
    assert items[0]["id"] == 1
    assert items[0]["reason"] == "invalid_predicate"
    assert items[0]["raw"]["subject"] == "测试主体"


def test_approve_quarantine_creates_active_claim(admin_client):
    kb_id = DEFAULT_IN_MEMORY_KB_ID
    orch = _cached_orchestrator(admin_client, kb_id)
    knowledge = orch.deps.knowledge
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
    quarantine_id = listed.json()[0]["id"]

    approved = admin_client.post(f"/admin/knowledge-bases/{kb_id}/quarantine/{quarantine_id}/approve")
    assert approved.status_code == 200, approved.text
    body = approved.json()
    claim = body["claim"]
    assert claim["status"] == "active"
    assert claim["subject"] == "七天无理由"
    assert claim["predicate"] == "运费承担方"
    assert claim["object"] == "卖家"

    stored = knowledge.get_claim(claim["id"])
    assert stored is not None
    assert stored.status == "active"
    assert admin_client.get(f"/admin/knowledge-bases/{kb_id}/quarantine").json() == []

    filtered = admin_client.get(
        f"/admin/knowledge-bases/{kb_id}/claims",
        params={"status": "active", "subject": "七天无理由"},
    )
    assert filtered.status_code == 200
    assert any(item["id"] == claim["id"] for item in filtered.json())


def test_approve_quarantine_reactivates_existing_claim(admin_client):
    kb_id = DEFAULT_IN_MEMORY_KB_ID
    orch = _cached_orchestrator(admin_client, kb_id)
    knowledge = orch.deps.knowledge

    claim = Claim(
        id="c-quarantine",
        family_id="f-quarantine",
        version=1,
        subject="定制商品",
        predicate="运费承担方",
        object="买家",
        subject_type="RefundRule",
        object_type="Concept",
        confidence=0.9,
        status="quarantined",
        valid_from=datetime.now(timezone.utc),
        valid_to=None,
        source_ids=["s1"],
    )
    knowledge.append_claim(claim)
    knowledge.add_quarantine("span_mismatch", {"claim_id": "c-quarantine", "source_id": "s1"})

    quarantine_id = knowledge.list_quarantine()[0]["id"]
    approved = admin_client.post(f"/admin/knowledge-bases/{kb_id}/quarantine/{quarantine_id}/approve")
    assert approved.status_code == 200
    assert approved.json()["claim"]["id"] == "c-quarantine"
    assert knowledge.get_claim("c-quarantine").status == "active"


def test_list_claims_filters_by_status_and_subject(admin_client):
    kb_id = DEFAULT_IN_MEMORY_KB_ID
    _seed_kb(admin_client, kb_id)

    response = admin_client.get(
        f"/admin/knowledge-bases/{kb_id}/claims",
        params={"status": "active"},
    )
    assert response.status_code == 200
    claims = response.json()
    assert claims
    assert all(item["status"] == "active" for item in claims)

    subject = claims[0]["subject"]
    filtered = admin_client.get(
        f"/admin/knowledge-bases/{kb_id}/claims",
        params={"status": "active", "subject": subject},
    )
    assert filtered.status_code == 200
    assert filtered.json()
    assert all(item["subject"] == subject for item in filtered.json())


def test_debug_ask_returns_trace(admin_client):
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


def test_debug_graph_neighbors(admin_client):
    kb_id = DEFAULT_IN_MEMORY_KB_ID
    orch = _cached_orchestrator(admin_client, kb_id)
    graph = orch.deps.graph
    entity_id = _entity_id("七天无理由", "RefundRule")
    neighbor_id = _entity_id("卖家", "Concept")
    graph.upsert_entity(entity_id, "RefundRule", {"name": "七天无理由"})
    graph.upsert_entity(neighbor_id, "Concept", {"name": "卖家"})
    graph.upsert_relation(entity_id, "运费承担方", neighbor_id, {})

    response = admin_client.get(f"/admin/knowledge-bases/{kb_id}/debug/graph/{entity_id}/neighbors")
    assert response.status_code == 200
    edges = response.json()
    assert len(edges) == 1
    assert edges[0]["predicate"] == "运费承担方"
    assert edges[0]["dst"] == neighbor_id
