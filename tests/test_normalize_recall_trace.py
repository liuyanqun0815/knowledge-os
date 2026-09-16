from __future__ import annotations

from unittest.mock import MagicMock

from orchestrator.nodes import normalize_node, recall_node, remember_node
from memory.ports import RecallContext


def test_normalize_node_trace_includes_input_and_output():
    ontology = MagicMock()
    ontology.normalize_term.side_effect = lambda alias: {"七天": "7天"}.get(alias, alias)
    domain = MagicMock()
    domain.get_aliases.return_value = ["七天"]
    deps = MagicMock()
    deps.ontology = ontology
    deps.domain = domain

    out = normalize_node({"question": "七天无理由退货吗"}, deps)

    assert out["normalized_question"] == "7天无理由退货吗"
    detail = out["trace"][0]["detail"]
    assert detail["input"] == "七天无理由退货吗"
    assert detail["output"] == "7天无理由退货吗"
    assert detail["changed"] is True
    assert detail["replacements"] == [{"from": "七天", "to": "7天"}]


def test_recall_node_trace_includes_episode_list():
    memory = MagicMock()
    memory.recall.return_value = RecallContext(
        episodes=[{"q": "能否退货", "a": "看类目"}],
        semantics=[],
    )
    deps = MagicMock()
    deps.memory = memory

    out = recall_node({"question": "退货多久", "session_id": "sess-1"}, deps)

    detail = out["trace"][0]["detail"]
    assert detail["session_id"] == "sess-1"
    assert detail["episode_count"] == 1
    assert detail["episodes"] == [{"q": "能否退货", "a": "看类目"}]
    assert "1 条历史" in out["trace"][0]["summary"]


def test_remember_node_persists_episode():
    memory = MagicMock()
    deps = MagicMock()
    deps.memory = memory
    answer = MagicMock()
    answer.text = "满减活动"
    state = {
        "question": "有什么活动？",
        "normalized_question": "有什么活动？",
        "session_id": "sess-1",
        "answer": answer,
        "trace": [],
    }

    out = remember_node(state, deps)

    memory.remember_episode.assert_called_once_with(
        "sess-1",
        {"q": "有什么活动？", "a": "满减活动"},
    )
    assert out["trace"][0]["status"] == "ok"
    assert out["trace"][0]["detail"]["episode"]["a"] == "满减活动"
