from fastapi.testclient import TestClient

from app.main import create_app


def test_ask_endpoint_after_ingest(tmp_path):
    app = create_app(data_root=str(tmp_path))
    client = TestClient(app)
    r = client.post(
        "/sources",
        json={"path": "samples/refund_policy_v3.md", "type": "policy"},
    )
    assert r.status_code == 200
    source_id = r.json()["source_id"]
    c = client.post(f"/sources/{source_id}/compile")
    assert c.status_code == 200
    assert c.json()["claims_created"] >= 1
    a = client.post("/ask", json={"question": "定制商品能否七天无理由退货？"})
    assert a.status_code == 200
    body = a.json()
    assert body["claim_ids"]
    assert body["evidence"]
