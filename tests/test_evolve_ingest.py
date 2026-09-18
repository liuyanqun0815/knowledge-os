from pathlib import Path

from akos.bootstrap import build_orchestrator_for_kb


def test_evolve_ingest_supersedes_freight_claim(seeded_kb_id):
    orch = build_orchestrator_for_kb(seeded_kb_id)
    v3_path = str(Path("tests/fixtures/refund_policy_v3.md"))
    v4_path = str(Path("tests/fixtures/refund_policy_v4.md"))
    v3_source_id = "refund_policy_v3"

    report_v3 = orch.ingest(v3_path, "policy")
    assert report_v3.claims_created >= 1

    active_before = orch.deps.knowledge.get_active_claims("七天无理由", "运费承担方")
    assert len(active_before) == 1
    assert active_before[0].object == "买家"
    old_claim_id = active_before[0].id

    report_v4 = orch.ingest(v4_path, "policy", replaces_source_id=v3_source_id)
    assert report_v4.claims_created >= 1

    v4_source = orch.deps.knowledge.get_source("refund_policy_v4")
    assert v4_source is not None
    assert v4_source.replaces_source_id == v3_source_id

    active_after = orch.deps.knowledge.get_active_claims("七天无理由", "运费承担方")
    assert len(active_after) == 1
    assert active_after[0].object == "平台"
    assert active_after[0].id != old_claim_id

    old_claim = orch.deps.knowledge.get_claim(old_claim_id)
    assert old_claim is not None
    assert old_claim.status == "superseded"
    assert active_after[0].version == 2
