from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from akos.interfaces.api.main import create_app
from akos.bootstrap import DEFAULT_IN_MEMORY_KB_ID, build_orchestrator_for_kb
from akos.domain.models.knowledge import Claim
from tests.conftest import ROOT, admin_upload_item

SAMPLE_MD = ROOT / "samples" / "refund_policy_v3.md"


def test_admin_lint_returns_report_after_upload(tmp_path, monkeypatch):
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

    response = client.get(f"/admin/knowledge-bases/{kb_id}/lint")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["kb_id"] == kb_id
    assert "summary" in body
    assert "issues" in body
    assert "checked_at" in body


def test_admin_lint_detects_conflict(tmp_path, monkeypatch):
    monkeypatch.delenv("ADMIN_API_TOKEN", raising=False)
    monkeypatch.setenv("AKOS_USE_PG", "false")
    monkeypatch.setenv("AKOS_EXTRACT_LLM", "false")
    monkeypatch.delenv("AKOS_LLM_API_KEY", raising=False)
    app = create_app(data_root=str(tmp_path))
    client = TestClient(app)
    kb_id = DEFAULT_IN_MEMORY_KB_ID

    orchestrator = build_orchestrator_for_kb(kb_id)
    knowledge = orchestrator.deps.knowledge
    knowledge.append_claim(
        Claim(
            id="claim-a",
            family_id="family-conflict",
            version=1,
            subject="七天无理由",
            predicate="运费承担方",
            object="买家",
            subject_type="RefundRule",
            object_type="Concept",
            confidence=0.9,
            status="active",
            valid_from=datetime.now(timezone.utc),
            valid_to=None,
            source_ids=[],
        )
    )
    knowledge.append_claim(
        Claim(
            id="claim-b",
            family_id="family-conflict",
            version=2,
            subject="七天无理由",
            predicate="运费承担方",
            object="平台",
            subject_type="RefundRule",
            object_type="Concept",
            confidence=0.9,
            status="active",
            valid_from=datetime.now(timezone.utc),
            valid_to=None,
            source_ids=[],
        )
    )
    app.state.orchestrator_cache[kb_id] = orchestrator

    response = client.get(f"/admin/knowledge-bases/{kb_id}/lint")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["summary"].get("conflict") == 1
    assert body["issues"][0]["code"] == "conflict"
