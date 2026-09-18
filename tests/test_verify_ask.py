from akos.bootstrap import build_orchestrator_for_kb


def test_ask_returns_verified_after_normal_ingest(seeded_kb_id):
    orch = build_orchestrator_for_kb(seeded_kb_id)
    report = orch.ingest("samples/refund_policy_v3.md", "policy")
    assert report.claims_created > 0

    answer = orch.ask("定制商品能否七天无理由退货？")

    assert answer.claim_ids
    assert answer.verification_status == "verified"
    assert answer.competing_claim_ids == []


def test_ask_returns_unverified_with_bad_evidence_quote(seeded_kb_id):
    orch = build_orchestrator_for_kb(seeded_kb_id)
    orch.ingest("samples/refund_policy_v3.md", "policy")

    for claim in orch.deps.knowledge.get_claims_for_source("refund_policy_v3"):
        source_id = claim.source_ids[0]
        orch.deps.evidence._bindings[claim.id] = [
            {
                "source_id": source_id,
                "start": 0,
                "end": 8,
                "quote": "完全不存在的引用",
                "weight": 0.5,
            }
        ]

    answer = orch.ask("定制商品能否七天无理由退货？")

    assert answer.verification_status == "unverified"
