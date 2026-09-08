from pathlib import Path

from infra.bootstrap import build_orchestrator_deps
from orchestrator.service import LangGraphOrchestrator


def test_ingest_then_ask_with_evidence():
    deps = build_orchestrator_deps()
    orchestrator = LangGraphOrchestrator(deps)
    report = orchestrator.ingest(str(Path("samples/refund_policy_v3.md")), "policy")
    assert report.claims_created >= 1
    answer = orchestrator.ask("定制商品能否七天无理由退货？", session_id="s1")
    assert answer.claim_ids
    assert answer.evidence
    assert answer.confidence > 0
    weak = orchestrator.ask("今天天气怎么样？", session_id="s1")
    assert weak.confidence < 0.4
    assert "依据不足" in weak.text or "不足" in weak.text
