from unittest.mock import MagicMock, patch

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
