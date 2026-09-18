from fastapi.testclient import TestClient

from akos.interfaces.api.main import create_app
from infra.bootstrap import DEFAULT_IN_MEMORY_KB_ID
from knowledge_base.models import KnowledgeBase


class ArchivedKnowledgeBaseRepo:
    def get(self, knowledge_base_id):
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        return KnowledgeBase(
            id=knowledge_base_id,
            name="archived",
            domain_type="generic",
            description="",
            status="archived",
            created_at=now,
            updated_at=now,
        )


def test_ask_requires_knowledge_base_id(tmp_path):
    app = create_app(data_root=str(tmp_path))
    client = TestClient(app)
    r = client.post("/ask", json={"question": "定制商品能否七天无理由退货？"})
    assert r.status_code == 422


def test_ask_endpoint_after_ingest(tmp_path):
    app = create_app(data_root=str(tmp_path))
    client = TestClient(app)
    kb_id = DEFAULT_IN_MEMORY_KB_ID
    r = client.post(
        "/sources",
        json={"knowledge_base_id": kb_id, "path": "samples/refund_policy_v3.md", "type": "policy"},
    )
    assert r.status_code == 200
    source_id = r.json()["source_id"]
    c = client.post(f"/sources/{source_id}/compile", json={"knowledge_base_id": kb_id})
    assert c.status_code == 200
    assert c.json()["claims_created"] >= 1
    a = client.post(
        "/ask",
        json={"knowledge_base_id": kb_id, "question": "定制商品能否七天无理由退货？"},
    )
    assert a.status_code == 200
    body = a.json()
    assert body["claim_ids"]
    assert body["evidence"]


def test_ask_rejects_archived_kb_even_when_orchestrator_is_cached(tmp_path, monkeypatch):
    app = create_app(data_root=str(tmp_path))
    cached_orchestrator = object()
    app.state.orchestrator_cache["archived-kb"] = cached_orchestrator
    monkeypatch.setattr("akos.interfaces.api.deps.get_kb_repo", lambda _request: ArchivedKnowledgeBaseRepo())
    client = TestClient(app)

    response = client.post(
        "/ask",
        json={"knowledge_base_id": "archived-kb", "question": "还能查询吗？"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "knowledge_base_not_active: archived-kb"
