from __future__ import annotations

from unittest.mock import MagicMock

from infra.settings import Settings
from akos.domain.ports.memory import RecallContext
from akos.application.ask.nodes import normalize_node, recall_node, remember_node
from akos.application.ask.question_rewrite import (
    matches_incomplete_pattern,
    question_has_domain_entity,
    try_llm_rewrite,
    try_rule_rewrite,
)


def test_incomplete_pattern_and_entity_guards():
    terms = ["定制商品", "七天无理由"]
    assert matches_incomplete_pattern("能退吗？")
    assert matches_incomplete_pattern("那时效呢")
    assert not matches_incomplete_pattern("定制商品能否七天无理由退货")
    assert question_has_domain_entity("定制商品能退吗", terms)
    assert not question_has_domain_entity("能退吗", terms)


def test_rule_rewrite_prepends_anchor_from_history():
    result = try_rule_rewrite(
        "能退吗？",
        episodes=[{"q": "定制商品七天无理由吗", "a": "定制商品不支持"}],
        terms=["定制商品", "七天无理由"],
    )
    assert result is not None
    assert result.method == "rule"
    assert result.anchor == "定制商品"
    assert result.text == "定制商品能退吗？"


def test_rule_rewrite_skips_when_entity_already_present():
    result = try_rule_rewrite(
        "定制商品能退吗",
        episodes=[{"q": "定制商品七天无理由吗", "a": "不支持"}],
        terms=["定制商品"],
    )
    assert result is None


def test_llm_rewrite_used_when_rule_misses(monkeypatch):
    monkeypatch.setattr(
        "akos.application.ask.nodes.get_settings",
        lambda: Settings(_env_file=None, ask_synthesis=True),
    )
    ontology = MagicMock()
    ontology.normalize_term.side_effect = lambda alias: alias
    ontology._types = {"个人信用贷款": "Product"}
    ontology._aliases = {}
    domain = MagicMock()
    domain.get_aliases.return_value = []
    llm = MagicMock()
    llm.is_configured = True
    llm.chat_completions.return_value = "个人信用贷款利率是多少"
    deps = MagicMock()
    deps.ontology = ontology
    deps.domain = domain
    deps.llm_client = llm

    # "利率呢" may match incomplete pattern - if rule finds anchor it wins.
    # Use a question that doesn't match incomplete patterns strongly...
    # Actually "利率是多少啊亲" might not match. Better: no episodes entity for rule
    # but wait - if incomplete and episodes have entity, rule wins.
    # For LLM path: incomplete pattern miss OR no anchor.
    # Use episodes without domain terms so rule can't find anchor.
    out = normalize_node(
        {
            "question": "刚才那个产品的费率怎么算的呀请详细说",
            "recall_episodes": [{"q": "随便问问天气", "a": "晴天"}],
        },
        deps,
    )

    # No domain entity in history → rule miss → LLM
    assert out["normalized_question"] == "个人信用贷款利率是多少"
    assert out["trace"][0]["detail"]["method"] == "llm"
    llm.chat_completions.assert_called_once()


def test_normalize_prefers_rule_over_llm(monkeypatch):
    monkeypatch.setattr(
        "akos.application.ask.nodes.get_settings",
        lambda: Settings(_env_file=None, ask_synthesis=True),
    )
    ontology = MagicMock()
    ontology.normalize_term.side_effect = lambda alias: alias
    ontology._types = {"定制商品": "Category"}
    ontology._aliases = {}
    domain = MagicMock()
    domain.get_aliases.return_value = []
    llm = MagicMock()
    llm.is_configured = True
    llm.chat_completions.return_value = "LLM不应被调用的结果"
    deps = MagicMock()
    deps.ontology = ontology
    deps.domain = domain
    deps.llm_client = llm

    out = normalize_node(
        {
            "question": "能退吗？",
            "recall_episodes": [{"q": "定制商品支持七天无理由吗", "a": "不支持"}],
        },
        deps,
    )

    assert out["normalized_question"] == "定制商品能退吗？"
    assert "rule" in out["trace"][0]["detail"]["method"]
    llm.chat_completions.assert_not_called()


def test_normalize_node_trace_includes_input_and_output(monkeypatch):
    monkeypatch.setattr(
        "akos.application.ask.nodes.get_settings",
        lambda: Settings(_env_file=None, ask_synthesis=False),
    )
    ontology = MagicMock()
    ontology.normalize_term.side_effect = lambda alias: {"七天": "7天"}.get(alias, alias)
    ontology._types = {}
    ontology._aliases = {}
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


def test_recall_node_puts_episodes_in_state():
    memory = MagicMock()
    memory.recall.return_value = RecallContext(
        episodes=[{"q": "能否退货", "a": "看类目"}],
        semantics=[],
    )
    deps = MagicMock()
    deps.memory = memory

    out = recall_node({"question": "退货多久", "session_id": "sess-1"}, deps)

    assert out["recall_episodes"] == [{"q": "能否退货", "a": "看类目"}]
    detail = out["trace"][0]["detail"]
    assert detail["episode_count"] == 1
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


def test_try_llm_rewrite_helper():
    llm = MagicMock()
    llm.is_configured = True
    llm.chat_completions.return_value = "个人信用贷款利率多少"
    result = try_llm_rewrite(
        "利率呢",
        episodes=[{"q": "个人信用贷款是什么", "a": "无抵押"}],
        llm_client=llm,
    )
    assert result is not None
    assert result.method == "llm"
    assert result.text == "个人信用贷款利率多少"
