from datetime import datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import create_app
from app.routes import get_ask_orchestrator
from orchestrator.service import AskResult


class FakeOrchestrator:
    def ask(
        self,
        question: str,
        session_id: str | None = None,
        as_of: datetime | None = None,
        include_trace: bool = False,
    ) -> SimpleNamespace | AskResult:
        answer = SimpleNamespace(
            text=f"answer: {question}",
            claim_ids=["claim-1"],
            evidence=[{"claim_id": "claim-1"}],
            confidence=0.9,
            retrieval_mode="hybrid",
            verification_status="verified",
            competing_claim_ids=[],
            procedure_id=None,
            as_of=as_of,
        )
        if include_trace:
            return AskResult(
                answer=answer,
                trace=[{"node": "retrieve"}, {"node": "verify", "verification_status": "verified"}],
            )
        return answer


def test_ask_requires_knowledge_base_id(tmp_path, monkeypatch):
    monkeypatch.delenv("ADMIN_API_TOKEN", raising=False)
    client = TestClient(create_app(data_root=str(tmp_path)))

    response = client.post("/ask", json={"question": "hello"})

    assert response.status_code == 422


def test_ask_response_may_include_trace_fields(tmp_path, monkeypatch):
    monkeypatch.delenv("ADMIN_API_TOKEN", raising=False)
    app = create_app(data_root=str(tmp_path))
    app.dependency_overrides[get_ask_orchestrator] = FakeOrchestrator
    client = TestClient(app)

    response = client.post(
        "/ask",
        json={
            "knowledge_base_id": "kb-1",
            "question": "定制商品能否退货？",
            "as_of": datetime(2026, 9, 8).isoformat(),
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert "text" in body
    assert "evidence" in body
    assert "request_id" in body
    assert "trace" in body


def test_admin_token_protects_ask_and_admin_routes(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMIN_API_TOKEN", "secret-token")
    client = TestClient(create_app(data_root=str(tmp_path)))

    ask_response = client.post(
        "/ask",
        json={"knowledge_base_id": "kb-1", "question": "hello"},
    )
    admin_response = client.get("/admin/knowledge-bases")

    assert ask_response.status_code == 401
    assert admin_response.status_code == 401


def test_admin_token_accepts_matching_header(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMIN_API_TOKEN", "secret-token")
    app = create_app(data_root=str(tmp_path))
    app.dependency_overrides[get_ask_orchestrator] = FakeOrchestrator
    client = TestClient(app)

    response = client.post(
        "/ask",
        headers={"X-Admin-Token": "secret-token"},
        json={"knowledge_base_id": "kb-1", "question": "hello"},
    )

    assert response.status_code == 200
