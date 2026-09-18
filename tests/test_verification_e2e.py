"""Phase 2.3 §7.5 acceptance: verification E2E."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from akos.interfaces.api.main import create_app
from akos.application.evolution.family import family_key
from akos.bootstrap import DEFAULT_IN_MEMORY_KB_ID, build_orchestrator_for_kb
from akos.domain.models.knowledge import Claim, Source, TextSpan
from akos.application.ask.nodes import verify_sample_node

V3_PATH = "tests/fixtures/refund_policy_v3.md"
V3_SOURCE_ID = "refund_policy_v3"
FREIGHT_FAMILY_ID = family_key("七天无理由", "运费承担方", "Concept")
BAD_QUOTE = "完全不存在的引用"


def _inject_bad_span_on_source_claims(orch, source_id: str, bad_quote: str = BAD_QUOTE) -> None:
    for claim in orch.deps.knowledge.get_claims_for_source(source_id):
        sid = claim.source_ids[0]
        orch.deps.evidence._bindings[claim.id] = [
            {
                "source_id": sid,
                "start": 0,
                "end": len(bad_quote),
                "quote": bad_quote,
                "weight": 0.5,
            }
        ]


def _seed_competing_freight_claims(deps) -> tuple[str, str]:
    source_id = "s-conflict"
    source_text = "买家承担退货运费。平台承担换货运费。"
    source = Source(
        id=source_id,
        title="policy",
        type="policy",
        uri="file://conflict",
        version="1",
        created_at=datetime.now(timezone.utc),
        status="ready",
    )
    deps.knowledge.save_source(source)
    deps.knowledge.save_source_text(source_id, source_text)

    now = datetime.now(timezone.utc)
    claim_buyer = Claim(
        id="c-freight-buyer",
        family_id=FREIGHT_FAMILY_ID,
        version=1,
        subject="七天无理由",
        predicate="运费承担方",
        object="买家",
        subject_type="RefundRule",
        object_type="Concept",
        confidence=0.9,
        status="active",
        valid_from=now,
        valid_to=None,
        source_ids=[source_id],
    )
    claim_platform = Claim(
        id="c-freight-platform",
        family_id=FREIGHT_FAMILY_ID,
        version=1,
        subject="七天无理由",
        predicate="运费承担方",
        object="平台",
        subject_type="RefundRule",
        object_type="Concept",
        confidence=0.9,
        status="active",
        valid_from=now,
        valid_to=None,
        source_ids=[source_id],
    )
    deps.knowledge.append_claim(claim_buyer)
    deps.knowledge.append_claim(claim_platform)
    deps.evidence.bind(
        claim_buyer.id,
        source_id,
        TextSpan(source_id, 0, 8, "买家承担退货运费"),
        0.9,
    )
    deps.evidence.bind(
        claim_platform.id,
        source_id,
        TextSpan(source_id, 9, 17, "平台承担换货运费"),
        0.9,
    )
    deps.retrieval.index_claim(claim_buyer)
    deps.retrieval.index_claim(claim_platform)
    return claim_buyer.id, claim_platform.id


def test_phase23_bad_span_returns_unverified_on_ask(seeded_kb_id):
    """§7.5.1: 手工注入 span 不符 Claim → ask 返回 verification_status=unverified."""
    orch = build_orchestrator_for_kb(seeded_kb_id)
    report = orch.ingest(V3_PATH, "policy")
    assert report.claims_created > 0

    _inject_bad_span_on_source_claims(orch, V3_SOURCE_ID)

    answer = orch.ask("定制商品能否七天无理由退货？")

    assert answer.verification_status == "unverified"
    assert answer.competing_claim_ids == []


def test_phase23_bad_span_quarantines_high_risk_on_verify_sample(seeded_kb_id):
    """§7.5.1 alt: 高风险谓词 span 不符 → verify_sample quarantine."""
    orch = build_orchestrator_for_kb(seeded_kb_id)
    deps = orch.deps
    source_id = "s-bad-high-risk"
    source_text = "七天无理由退货运费承担方为买家。"

    source = Source(
        id=source_id,
        title="policy",
        type="policy",
        uri="file://bad",
        version="1",
        created_at=datetime.now(timezone.utc),
        status="ready",
    )
    deps.knowledge.save_source(source)
    deps.knowledge.save_source_text(source_id, source_text)

    claim = Claim(
        id="c-bad-high-risk",
        family_id=FREIGHT_FAMILY_ID,
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
        source_ids=[source_id],
    )
    deps.knowledge.append_claim(claim)
    deps.evidence.bind(claim.id, source_id, TextSpan(source_id, 0, 5, BAD_QUOTE), 0.9)
    deps.retrieval.index_claim(claim)

    quarantine_before = len(deps.knowledge.list_quarantine())
    result = verify_sample_node({"source_id": source_id, "error": None}, deps)

    assert len(deps.knowledge.list_quarantine()) == quarantine_before + 1
    assert result["verify_report"]["quarantined"] == 1
    assert deps.knowledge.get_claim(claim.id).status == "quarantined"


def test_phase23_competing_claims_return_conflict(seeded_kb_id):
    """§7.5.2: 同 family 多条 active Claim → conflict + competing_claim_ids."""
    orch = build_orchestrator_for_kb(seeded_kb_id)
    claim_buyer_id, claim_platform_id = _seed_competing_freight_claims(orch.deps)

    answer = orch.ask("七天无理由退货运费承担方是谁？")

    assert answer.verification_status == "conflict"
    assert set(answer.competing_claim_ids) == {claim_buyer_id, claim_platform_id}
    assert set(answer.competing_claim_ids).issubset(set(answer.claim_ids))


def test_phase23_ask_include_trace_query_param(tmp_path, monkeypatch):
    """§7.5.3: POST /ask?include_trace=true 返回含 node 名的 trace JSON."""
    monkeypatch.delenv("ADMIN_API_TOKEN", raising=False)
    app = create_app(data_root=str(tmp_path))
    client = TestClient(app)
    kb_id = DEFAULT_IN_MEMORY_KB_ID

    source_response = client.post(
        "/sources",
        json={"knowledge_base_id": kb_id, "path": V3_PATH, "type": "policy"},
    )
    assert source_response.status_code == 200
    source_id = source_response.json()["source_id"]

    compile_response = client.post(f"/sources/{source_id}/compile", json={"knowledge_base_id": kb_id})
    assert compile_response.status_code == 200

    ask_response = client.post(
        "/ask?include_trace=true",
        json={"knowledge_base_id": kb_id, "question": "定制商品能否七天无理由退货？"},
    )
    assert ask_response.status_code == 200
    body = ask_response.json()

    assert body["trace"] is not None
    assert isinstance(body["trace"], list)
    node_names = {entry["node"] for entry in body["trace"]}
    assert "retrieve" in node_names
    assert "verify" in node_names
    assert body["verification_status"] == "verified"
