"""Path-based wiki topic links (hierarchy, no topic- prefix)."""

from __future__ import annotations

from wiki.links import topic_page_name, topic_page_path, topic_wikilink, wiki_page_path


def test_wiki_page_path_preserves_nested_folder_segments() -> None:
    assert wiki_page_path("贷款产品/贷款产品合集", "_index") == "贷款产品/贷款产品合集/_index"
    assert wiki_page_path("贷款产品/贷款产品合集", "个人信用贷款") == "贷款产品/贷款产品合集/个人信用贷款"


def test_wiki_page_path_sanitizes_each_segment_only() -> None:
    assert wiki_page_path("a/b:c", "d?e") == "a/b_c/d_e"


def test_topic_page_path_hub_only_uses_index() -> None:
    assert topic_page_path("客服话术") == "客服话术/_index"
    assert topic_page_path("客服话术", leaf=None) == "客服话术/_index"


def test_topic_page_path_hub_leaf() -> None:
    assert topic_page_path("客服话术", "沟通规范") == "客服话术/沟通规范"


def test_topic_page_path_sanitizes_unsafe_chars() -> None:
    assert topic_page_path("a/b", "c:d") == "a_b/c_d"


def test_topic_wikilink_hub_leaf_default_label() -> None:
    assert topic_wikilink("客服话术", "沟通规范") == "[[客服话术/沟通规范|沟通规范]]"


def test_topic_wikilink_hub_only_default_label() -> None:
    assert topic_wikilink("客服话术") == "[[客服话术/_index|客服话术]]"


def test_topic_wikilink_custom_label() -> None:
    assert topic_wikilink("客服话术", "沟通规范", label="规范") == "[[客服话术/沟通规范|规范]]"


def test_topic_wikilink_legacy_flat_when_hierarchy_disabled() -> None:
    assert topic_wikilink("尺码选择", hierarchy_enabled=False) == "[[topic-尺码选择|尺码选择]]"


def test_topic_page_name_keeps_legacy_prefix() -> None:
    assert topic_page_name("尺码选择") == "topic-尺码选择"
