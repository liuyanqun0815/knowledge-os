from wiki.layout import (
    BUILTIN_WIKI_FOLDERS,
    classify_folder,
    extract_catalog_items,
    extract_chapter_items,
    resolve_wiki_layout,
    should_split_source,
)


def test_builtin_wiki_folders_has_at_least_twenty_named_categories():
    named = [name for name in BUILTIN_WIKI_FOLDERS if name != "未分类"]
    assert len(named) >= 20
    assert "理财产品" in BUILTIN_WIKI_FOLDERS
    assert "贷款产品" in BUILTIN_WIKI_FOLDERS


def test_classify_folder_picks_wealth_and_loan_categories():
    assert classify_folder("本理财计划净值型产品说明书，托管人负责保管", "成就系列.md") == "理财产品"
    assert classify_folder("个人信用贷款最高额度与年利率说明", "贷款产品合集.md") == "贷款产品"


def test_should_split_source_uses_5000_char_threshold():
    short = "章节\n" * 100
    assert should_split_source(short, min_chars=5000) is False
    long_text = "一、风险揭示\n" + ("内容" * 2600)
    assert len(long_text) >= 5000
    assert should_split_source(long_text, min_chars=5000) is True


def test_resolve_wiki_layout_product_bundle_for_long_manual():
    text = "一、风险揭示\n二、产品要素\n三、投资范围\n四、费用\n" + ("详细条款" * 1300)
    decision = resolve_wiki_layout(
        "src-wealth",
        "青银理财成就系列（低波共享）.md",
        text,
        min_chars=5000,
    )
    assert decision.split_mode == "product_bundle"
    assert decision.category == "理财产品"
    assert decision.folder == "理财产品/青银理财成就系列（低波共享）"
    assert decision.default_slug == "_index"


def test_resolve_wiki_layout_single_page_for_short_doc():
    decision = resolve_wiki_layout(
        "src-short",
        "话术开场白.md",
        "客服话术开场白示例。",
        min_chars=5000,
    )
    assert decision.split_mode == "single"
    assert decision.folder == "客服话术"
    assert decision.default_slug == "话术开场白"


def test_extract_catalog_items_from_numbered_loan_products():
    text = "\n".join(
        [
            "# 贷款产品知识库",
            "## 概述",
            "总述",
            "## 1. 个人信用贷款",
            "信用贷正文",
            "## 2. 房屋抵押贷款",
            "房贷正文",
            "## 3. 汽车贷款",
            "车贷正文",
            "## 常见问题",
            "问答",
        ]
    )
    items = extract_catalog_items(text)
    assert [item.title for item in items] == [
        "个人信用贷款",
        "房屋抵押贷款",
        "汽车贷款",
    ]
    assert "信用贷正文" in items[0].body


def test_resolve_wiki_layout_catalog_bundle_for_product_collection():
    text = "\n".join(
        [
            "## 1. 个人信用贷款",
            "信用贷" * 800,
            "## 2. 房屋抵押贷款",
            "房贷" * 800,
            "## 3. 汽车贷款",
            "车贷" * 800,
        ]
    )
    decision = resolve_wiki_layout(
        "贷款产品合集",
        "贷款产品合集.md",
        text,
        min_chars=5000,
    )
    assert decision.split_mode == "catalog_bundle"
    assert decision.folder == "贷款产品/贷款产品合集"
    assert decision.default_slug == "_index"


def test_extract_chapter_items_from_chinese_manual_sections():
    text = "\n".join(
        [
            "前言",
            "一、风险揭示",
            "风险正文" * 20,
            "二、产品要素",
            "要素正文" * 20,
            "三、投资范围",
            "投资正文" * 20,
            "四、费用",
            "费用正文" * 20,
        ]
    )
    items = extract_chapter_items(text)
    assert [item.title for item in items] == ["风险揭示", "产品要素", "投资范围", "费用"]
    assert "风险正文" in items[0].body


def test_resolve_wiki_layout_product_bundle_for_long_manual_detects_chapters():
    text = "\n".join(
        [
            "一、风险揭示",
            "风险内容" * 50,
            "二、产品要素",
            "要素内容" * 50,
            "三、投资范围",
            "投资内容" * 50,
            "四、费用",
            "费用内容" * 50,
            "详细条款" * 800,
        ]
    )
    decision = resolve_wiki_layout(
        "src-wealth",
        "青银理财成就系列（低波共享）.md",
        text,
        min_chars=5000,
    )
    assert decision.split_mode == "product_bundle"
    assert len(extract_chapter_items(text)) >= 4
