from datetime import datetime, timezone
from pathlib import Path

from akos.bootstrap import build_orchestrator_for_kb
from akos.application.ask.nodes import parse_time_node


def test_as_of_before_v4_effective_returns_buyer_not_platform(seeded_kb_id):
    orch = build_orchestrator_for_kb(seeded_kb_id)
    v3_path = str(Path("samples/refund_policy_v3.md"))
    v4_path = str(Path("samples/refund_policy_v4.md"))

    orch.ingest(v3_path, "policy")
    active_v3 = orch.deps.knowledge.get_active_claims("七天无理由", "运费承担方")
    assert len(active_v3) == 1
    assert active_v3[0].object == "买家"
    old_claim_id = active_v3[0].id

    orch.ingest(v4_path, "policy", replaces_source_id="refund_policy_v3")

    active_after = orch.deps.knowledge.get_active_claims("七天无理由", "运费承担方")
    assert len(active_after) == 1
    assert active_after[0].object == "平台"

    old_claim = orch.deps.knowledge.get_claim(old_claim_id)
    assert old_claim is not None
    as_of_time = old_claim.valid_from
    assert as_of_time is not None

    historical = orch.ask("七天无理由退货运费承担方是谁？", as_of=as_of_time)
    assert "买家" in historical.text
    assert "平台" not in historical.text
    assert historical.as_of == as_of_time


def test_parse_time_node_uses_body_as_of_over_question():
    explicit = datetime(2024, 3, 15, tzinfo=timezone.utc)
    result = parse_time_node(
        {"question": "2024年运费谁承担？", "as_of": explicit},
        deps=None,
    )
    assert result == {}


def test_parse_time_node_parses_year_from_question():
    result = parse_time_node({"question": "2024年七天无理由退货运费谁承担？", "as_of": None}, deps=None)
    assert result["as_of"] == datetime(2024, 6, 30, tzinfo=timezone.utc)


def test_parse_time_node_parses_dangshi_keyword():
    result = parse_time_node({"question": "当时的运费承担方是谁？", "as_of": None}, deps=None)
    assert "as_of" in result
    assert result["as_of"] is not None
