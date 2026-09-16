from fastapi.testclient import TestClient

from app.main import create_app
from infra.bootstrap import build_orchestrator_for_kb, DEFAULT_IN_MEMORY_KB_ID


def test_ask_with_include_trace_returns_node_names(seeded_kb_id):
    orch = build_orchestrator_for_kb(seeded_kb_id)
    report = orch.ingest("samples/refund_policy_v3.md", "policy")
    assert report.claims_created > 0

    result = orch.ask("定制商品能否七天无理由退货？", include_trace=True)

    assert result.trace
    node_names = {entry["node"] for entry in result.trace}
    assert "retrieve" in node_names
    assert "verify" in node_names
    assert result.answer.duration_ms is not None
    assert result.answer.duration_ms >= 0


def test_ask_api_includes_verification_status_and_trace(tmp_path):
    app = create_app(data_root=str(tmp_path))
    client = TestClient(app)
    kb_id = DEFAULT_IN_MEMORY_KB_ID

    source_response = client.post(
        "/sources",
        json={"knowledge_base_id": kb_id, "path": "samples/refund_policy_v3.md", "type": "policy"},
    )
    assert source_response.status_code == 200
    source_id = source_response.json()["source_id"]

    compile_response = client.post(f"/sources/{source_id}/compile", json={"knowledge_base_id": kb_id})
    assert compile_response.status_code == 200

    ask_response = client.post(
        "/ask",
        json={
            "knowledge_base_id": kb_id,
            "question": "定制商品能否七天无理由退货？",
            "include_trace": True,
        },
    )
    assert ask_response.status_code == 200
    body = ask_response.json()

    assert body["verification_status"] == "verified"
    assert body["competing_claim_ids"] == []
    assert body["trace"] is not None
    assert isinstance(body.get("duration_ms"), int)
    assert body["duration_ms"] >= 0
    node_names = {entry["node"] for entry in body["trace"]}
    assert "retrieve" in node_names
    assert "verify" in node_names


def test_ask_api_include_trace_query_param(tmp_path):
    app = create_app(data_root=str(tmp_path))
    client = TestClient(app)
    kb_id = DEFAULT_IN_MEMORY_KB_ID

    source_response = client.post(
        "/sources",
        json={"knowledge_base_id": kb_id, "path": "samples/refund_policy_v3.md", "type": "policy"},
    )
    source_id = source_response.json()["source_id"]
    client.post(f"/sources/{source_id}/compile", json={"knowledge_base_id": kb_id})

    ask_response = client.post(
        "/ask?include_trace=true",
        json={"knowledge_base_id": kb_id, "question": "定制商品能否七天无理由退货？"},
    )
    assert ask_response.status_code == 200
    body = ask_response.json()
    assert body["trace"] is not None
    assert any(entry["node"] == "verify" for entry in body["trace"])
