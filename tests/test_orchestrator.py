from pathlib import Path

from akos.bootstrap import build_orchestrator_for_kb


def test_ingest_then_ask_with_evidence(seeded_kb_id):
    orchestrator = build_orchestrator_for_kb(seeded_kb_id)
    report = orchestrator.ingest(str(Path("tests/fixtures/refund_policy_v3.md")), "policy")
    assert report.claims_created >= 1
    answer = orchestrator.ask("定制商品能否七天无理由退货？", session_id="s1")
    assert answer.claim_ids
    assert answer.evidence
    assert answer.confidence > 0
    weak = orchestrator.ask("今天天气怎么样？", session_id="s1")
    assert not weak.claim_ids
    assert weak.confidence < 0.8


def test_build_orchestrator_for_kb_has_domain(seeded_kb_id):
    orchestrator = build_orchestrator_for_kb(seeded_kb_id)
    assert orchestrator.deps.domain.name == "ecommerce_cs"
    assert orchestrator.deps.knowledge_base_id == seeded_kb_id
