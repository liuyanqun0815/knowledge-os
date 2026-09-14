from __future__ import annotations

from domains.ecommerce_cs.wiki_hierarchy import get_ecommerce_wiki_seeds
from wiki.hierarchy import assign_wiki_hierarchy


def test_seeded_snippet_maps_to_forbidden_expressions():
    seeds = get_ecommerce_wiki_seeds()
    plan = assign_wiki_hierarchy(["不知道"], seeds=seeds)

    a = plan.assignments["不知道"]
    assert a.role == "snippet"
    assert a.hub == "客服话术"
    assert a.leaf is None
    assert a.target_leaf == "禁用表达"
    assert "禁用表达" in plan.hubs["客服话术"]


def test_unknown_short_phrase_becomes_snippet():
    plan = assign_wiki_hierarchy(["短词"], seeds=None)

    a = plan.assignments["短词"]
    assert a.role == "snippet"
    assert a.hub == "未分类"
    assert a.leaf is None


def test_unknown_short_phrase_uses_most_frequent_hub():
    seeds = get_ecommerce_wiki_seeds()
    plan = assign_wiki_hierarchy(["客服沟通", "短词"], seeds=seeds)

    a = plan.assignments["短词"]
    assert a.role == "snippet"
    assert a.hub == "客服话术"


def test_seeded_leaf_opening_and_communication():
    seeds = get_ecommerce_wiki_seeds()
    plan = assign_wiki_hierarchy(["客服开场", "开场", "客服沟通"], seeds=seeds)

    opening = plan.assignments["客服开场"]
    assert opening.role == "leaf"
    assert opening.hub == "客服话术"
    assert opening.leaf == "开场"

    assert plan.assignments["开场"].leaf == "开场"
    assert plan.assignments["客服沟通"].leaf == "沟通规范"
    assert set(plan.hubs["客服话术"]) >= {"开场", "沟通规范"}


def test_escalation_rank_heuristic():
    plan = assign_wiki_hierarchy(["一级在线客服", "二级客服主管"], seeds=None)

    first = plan.assignments["一级在线客服"]
    assert first.role == "leaf"
    assert first.hub == "投诉升级"
    assert first.leaf == "一级在线客服"
    assert "一级在线客服" in plan.hubs["投诉升级"]


def test_unmapped_long_name_becomes_hub_only():
    plan = assign_wiki_hierarchy(["尺码选择指南手册"], seeds=None)

    a = plan.assignments["尺码选择指南手册"]
    assert a.role == "hub"
    assert a.hub == "尺码选择指南手册"
    assert a.leaf is None
    assert plan.hubs["尺码选择指南手册"] == []
