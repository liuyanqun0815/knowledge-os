from infra.bootstrap import build_default_orchestrator


def test_mvp_success_criterion():
    orch = build_default_orchestrator()
    report = orch.ingest("samples/refund_policy_v3.md", "policy")
    assert report.claims_created > 0
    assert report.quarantined >= 0
    answer = orch.ask("定制商品能否七天无理由退货？")
    assert answer.claim_ids
    assert any("quote" in e for e in answer.evidence)
    assert 0 < answer.confidence <= 1
