from fastapi.testclient import TestClient

from app.main import create_app
from infra.bootstrap import DEFAULT_IN_MEMORY_KB_ID


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
