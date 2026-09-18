"""Phase 2.2 §6.5 acceptance: v3→v4 evolution E2E."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from akos.interfaces.api.main import create_app
from akos.application.evolution.family import family_key
from infra.bootstrap import DEFAULT_IN_MEMORY_KB_ID, build_orchestrator_for_kb
from tests.conftest import admin_upload_item

V3_PATH = Path("samples/refund_policy_v3.md")
V4_PATH = Path("samples/refund_policy_v4.md")
V3_SOURCE_ID = "refund_policy_v3"
FREIGHT_FAMILY_ID = family_key("七天无理由", "运费承担方", "Concept")


def _ingest_v3_then_v4(orch) -> tuple[str, str]:
    orch.ingest(str(V3_PATH), "policy")
    active_v3 = orch.deps.knowledge.get_active_claims("七天无理由", "运费承担方")
    assert len(active_v3) == 1
    assert active_v3[0].object == "买家"
    old_claim_id = active_v3[0].id

    orch.ingest(str(V4_PATH), "policy", replaces_source_id=V3_SOURCE_ID)

    active_after = orch.deps.knowledge.get_active_claims("七天无理由", "运费承担方")
    assert len(active_after) == 1
    assert active_after[0].object == "平台"
    assert active_after[0].version == 2
    assert active_after[0].id != old_claim_id

    old_claim = orch.deps.knowledge.get_claim(old_claim_id)
    assert old_claim is not None
    assert old_claim.status == "superseded"
    return old_claim_id, active_after[0].id


def test_phase22_v3_to_v4_supersedes_freight_carrier(seeded_kb_id):
    """§6.5.1-2: v3→v4 supersede 运费承担方；active claim 为新值「平台」."""
    orch = build_orchestrator_for_kb(seeded_kb_id)
    _ingest_v3_then_v4(orch)

    v4_source = orch.deps.knowledge.get_source("refund_policy_v4")
    assert v4_source is not None
    assert v4_source.replaces_source_id == V3_SOURCE_ID


def test_phase22_as_of_returns_v3_buyer_value(seeded_kb_id):
    """§6.5.3: as_of(v3 生效日) 仍返回「买家」."""
    orch = build_orchestrator_for_kb(seeded_kb_id)

    orch.ingest(str(V3_PATH), "policy")
    v3_claim = orch.deps.knowledge.get_active_claims("七天无理由", "运费承担方")[0]
    as_of_time = v3_claim.valid_from
    assert as_of_time is not None

    orch.ingest(str(V4_PATH), "policy", replaces_source_id=V3_SOURCE_ID)

    current = orch.ask("七天无理由退货运费承担方是谁？")
    assert "平台" in current.text

    historical_claim = orch.deps.knowledge.as_of(as_of_time, FREIGHT_FAMILY_ID)
    assert historical_claim is not None
    assert historical_claim.object == "买家"

    historical_answer = orch.ask("七天无理由退货运费承担方是谁？", as_of=as_of_time)
    assert "买家" in historical_answer.text
    assert "平台" not in historical_answer.text
    assert historical_answer.as_of == as_of_time


def test_phase22_claim_history_two_versions(seeded_kb_id):
    """§6.5.4: claim history 时间线 2 版本（排除 staging）."""
    orch = build_orchestrator_for_kb(seeded_kb_id)
    _ingest_v3_then_v4(orch)

    history = orch.deps.knowledge.get_claim_history(FREIGHT_FAMILY_ID)
    visible = [claim for claim in history if claim.status != "staging"]
    assert len(visible) == 2

    by_version = sorted(visible, key=lambda claim: claim.version)
    assert by_version[0].object == "买家"
    assert by_version[0].status == "superseded"
    assert by_version[0].version == 1
    assert by_version[1].object == "平台"
    assert by_version[1].status == "active"
    assert by_version[1].version == 2


def test_phase22_evolution_e2e_http(tmp_path, monkeypatch):
    """HTTP E2E: upload v3/v4、public history API、ask as_of."""
    monkeypatch.delenv("ADMIN_API_TOKEN", raising=False)
    app = create_app(data_root=str(tmp_path))
    client = TestClient(app)
    kb_id = DEFAULT_IN_MEMORY_KB_ID

    with V3_PATH.open("rb") as handle:
        upload_v3 = client.post(
            f"/admin/knowledge-bases/{kb_id}/sources/upload",
            files={"file": ("refund_policy_v3.md", handle, "text/markdown")},
            data={"source_type": "policy"},
        )
    assert upload_v3.status_code == 202, upload_v3.text
    v3_source_id = admin_upload_item(upload_v3)["source_id"]

    with V4_PATH.open("rb") as handle:
        upload_v4 = client.post(
            f"/admin/knowledge-bases/{kb_id}/sources/upload",
            files={"file": ("refund_policy_v4.md", handle, "text/markdown")},
            data={"source_type": "policy", "replaces_source_id": v3_source_id},
        )
    assert upload_v4.status_code == 202, upload_v4.text

    history = client.get(
        f"/claims/{FREIGHT_FAMILY_ID}/history",
        params={"knowledge_base_id": kb_id},
    )
    assert history.status_code == 200, history.text
    items = history.json()
    assert len(items) == 2
    assert items[0]["object"] == "买家"
    assert items[0]["status"] == "superseded"
    assert items[1]["object"] == "平台"
    assert items[1]["status"] == "active"

    admin_history = client.get(f"/admin/knowledge-bases/{kb_id}/claims/{FREIGHT_FAMILY_ID}/history")
    assert admin_history.status_code == 200, admin_history.text
    assert len(admin_history.json()) == 2

    current_ask = client.post(
        "/ask",
        json={"knowledge_base_id": kb_id, "question": "七天无理由退货运费承担方是谁？"},
    )
    assert current_ask.status_code == 200, current_ask.text
    assert "平台" in current_ask.json()["text"]

    as_of_time = items[0]["valid_from"]
    historical_ask = client.post(
        "/ask",
        json={
            "knowledge_base_id": kb_id,
            "question": "七天无理由退货运费承担方是谁？",
            "as_of": as_of_time,
        },
    )
    assert historical_ask.status_code == 200, historical_ask.text
    body = historical_ask.json()
    assert "买家" in body["text"]
    assert body["as_of"] is not None
