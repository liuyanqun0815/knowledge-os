from pathlib import Path
from unittest.mock import MagicMock, patch

from infra.bootstrap import build_orchestrator_for_kb
from orchestrator.nodes import remember_node


def test_remember_node_skips_persistence():
    memory = MagicMock()
    deps = MagicMock()
    deps.memory = memory
    state = {
        "question": "有什么活动？",
        "session_id": "sess-1",
        "answer": MagicMock(text="满减活动"),
        "trace": [],
    }
    with patch("orchestrator.nodes.memory_agent.remember") as remember_mock:
        out = remember_node(state, deps)
        remember_mock.assert_not_called()
    memory.remember_episode.assert_not_called()
    steps = out.get("trace") or []
    assert len(steps) == 1
    assert steps[0]["node"] == "remember"
    assert steps[0]["status"] == "skipped"
    assert steps[0]["duration_ms"] == 0


def test_ask_trace_steps_include_non_negative_duration_ms(seeded_kb_id):
    orchestrator = build_orchestrator_for_kb(seeded_kb_id)
    report = orchestrator.ingest(str(Path("samples/refund_policy_v3.md")), "policy")
    assert report.claims_created >= 1

    result = orchestrator.ask("定制商品能否七天无理由退货？", include_trace=True)

    assert result.trace
    assert result.answer is not None
    assert result.answer.duration_ms is not None
    assert isinstance(result.answer.duration_ms, int)
    assert result.answer.duration_ms >= 0

    for step in result.trace:
        assert "duration_ms" in step, f"missing duration_ms on node={step.get('node')}"
        assert isinstance(step["duration_ms"], int)
        assert step["duration_ms"] >= 0

    node_names = {entry["node"] for entry in result.trace}
    for required in ("route_mode", "retrieve", "verify", "answer", "remember"):
        assert required in node_names


def test_ask_answer_includes_wall_clock_duration_ms(seeded_kb_id):
    orchestrator = build_orchestrator_for_kb(seeded_kb_id)
    report = orchestrator.ingest(str(Path("samples/refund_policy_v3.md")), "policy")
    assert report.claims_created >= 1

    answer = orchestrator.ask("定制商品能否七天无理由退货？", include_trace=False)

    assert answer.duration_ms is not None
    assert isinstance(answer.duration_ms, int)
    assert answer.duration_ms >= 0
