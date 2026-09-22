from pathlib import Path

from akos.application.wiki.meta import WikiPageMeta, save_pages_meta


def _seed(wiki: Path) -> None:
    (wiki / "售后").mkdir(parents=True)
    (wiki / "售后" / "七天无理由退货.md").write_text(
        "# 七天\n\n## 摘要\n\n退款说明在此。\n", encoding="utf-8"
    )
    (wiki / "index.md").write_text(
        "---\nkb_id: kb1\n---\n\n## 主题\n\n### 售后\n> 涵盖七天无理由退货。\n"
        "- [[售后/七天无理由退货|七天无理由退货]] — 退款说明在此。\n",
        encoding="utf-8",
    )
    save_pages_meta(
        wiki,
        {
            "售后/七天无理由退货": WikiPageMeta(
                path="售后/七天无理由退货.md",
                title="七天无理由退货",
                kind="source_page",
                content_hash="h",
                source_ids=["s1"],
                hub="售后",
                summary="退款说明在此。",
            )
        },
    )


def test_resolve_rejects_traversal(tmp_path: Path):
    from akos.application.wiki.browser import resolve_wiki_page_path

    wiki = tmp_path / "wiki"
    wiki.mkdir()
    try:
        resolve_wiki_page_path(wiki, "../secrets")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_build_tree_groups_by_hub(tmp_path: Path):
    from akos.application.wiki.browser import build_wiki_tree

    wiki = tmp_path / "wiki"
    _seed(wiki)
    tree = build_wiki_tree(wiki)
    hub = next(h for h in tree["hubs"] if h["name"] == "售后")
    assert hub["pages"][0]["page_id"] == "售后/七天无理由退货"


def test_search_matches_body_snippet(tmp_path: Path):
    from akos.application.wiki.browser import search_wiki_pages

    wiki = tmp_path / "wiki"
    _seed(wiki)
    result = search_wiki_pages(wiki, "退款")
    assert result["total"] >= 1
    assert result["hits"][0]["page_id"] == "售后/七天无理由退货"
    assert any("退款" in s for s in result["hits"][0]["snippets"])


def test_search_empty_query(tmp_path: Path):
    from akos.application.wiki.browser import search_wiki_pages

    wiki = tmp_path / "wiki"
    _seed(wiki)
    for query in ("", "   "):
        result = search_wiki_pages(wiki, query)
        assert result["total"] == 0
        assert result["hits"] == []


def test_build_tree_hub_description(tmp_path: Path):
    from akos.application.wiki.browser import build_wiki_tree

    wiki = tmp_path / "wiki"
    _seed(wiki)
    tree = build_wiki_tree(wiki)
    hub = next(h for h in tree["hubs"] if h["name"] == "售后")
    assert hub["description"] == "涵盖七天无理由退货。"


def test_search_title_ranks_above_body(tmp_path: Path):
    from akos.application.wiki.browser import search_wiki_pages

    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "a.md").write_text("# body only\n\nuniquebodyword here.\n", encoding="utf-8")
    (wiki / "b.md").write_text("# Title\n\nother content.\n", encoding="utf-8")
    save_pages_meta(
        wiki,
        {
            "a": WikiPageMeta(
                path="a.md",
                title="Other Title",
                kind="source_page",
                content_hash="h1",
                source_ids=["s1"],
                summary="no match",
            ),
            "b": WikiPageMeta(
                path="b.md",
                title="uniquebodyword Match",
                kind="source_page",
                content_hash="h2",
                source_ids=["s2"],
                summary="no match",
            ),
        },
    )
    result = search_wiki_pages(wiki, "uniquebodyword")
    assert result["total"] == 2
    assert result["hits"][0]["page_id"] == "b"
    assert result["hits"][1]["page_id"] == "a"


def test_search_clamps_limit_to_100(tmp_path: Path):
    from akos.application.wiki.browser import search_wiki_pages

    wiki = tmp_path / "wiki"
    wiki.mkdir()
    meta: dict[str, WikiPageMeta] = {}
    for i in range(150):
        name = f"page{i}"
        (wiki / f"{name}.md").write_text(f"# {name}\n\ncommonneedle\n", encoding="utf-8")
        meta[name] = WikiPageMeta(
            path=f"{name}.md",
            title=name,
            kind="source_page",
            content_hash=f"h{i}",
            source_ids=[f"s{i}"],
        )
    save_pages_meta(wiki, meta)
    result = search_wiki_pages(wiki, "commonneedle", limit=200)
    assert result["total"] == 150
    assert len(result["hits"]) == 100


def test_build_tree_uses_meta_hub_for_flat_page_id(tmp_path: Path):
    from akos.application.wiki.browser import build_wiki_tree

    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "flat.md").write_text("# Flat\n", encoding="utf-8")
    save_pages_meta(
        wiki,
        {
            "flat": WikiPageMeta(
                path="flat.md",
                title="Flat",
                kind="source_page",
                content_hash="h",
                source_ids=["s1"],
                hub="售后",
            )
        },
    )
    tree = build_wiki_tree(wiki)
    hub = next(h for h in tree["hubs"] if h["name"] == "售后")
    assert hub["pages"][0]["page_id"] == "flat"


def test_build_tree_includes_index_when_present(tmp_path: Path):
    from akos.application.wiki.browser import build_wiki_tree, read_wiki_page

    wiki = tmp_path / "wiki"
    _seed(wiki)
    tree = build_wiki_tree(wiki)
    page_ids = [p["page_id"] for h in tree["hubs"] for p in h["pages"]]
    assert "index" in page_ids
    overview = next(h for h in tree["hubs"] if h["name"] == "总览")
    assert overview["pages"][0]["page_id"] == "index"
    assert overview["pages"][0]["title"] == "综合概览"
    page = read_wiki_page(wiki, "index")
    assert page["page_id"] == "index"
    assert page["path"] == "index.md"
    assert page["title"] == "综合概览"


def test_build_tree_nests_product_bundles_under_category(tmp_path: Path):
    from akos.application.wiki.browser import build_wiki_tree

    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "贷款产品").mkdir()
    (wiki / "贷款产品" / "工行融e借.md").write_text("# 融e借\n", encoding="utf-8")
    bundle = wiki / "贷款产品" / "招商银行闪电贷"
    bundle.mkdir()
    (bundle / "_index.md").write_text("# 闪电贷\n", encoding="utf-8")
    (bundle / "申请条件.md").write_text("# 申请条件\n", encoding="utf-8")
    save_pages_meta(
        wiki,
        {
            "贷款产品/工行融e借": WikiPageMeta(
                path="贷款产品/工行融e借.md",
                title="工行融e借",
                kind="source_page",
                content_hash="h1",
                source_ids=["rong"],
                hub="贷款产品",
            ),
            "贷款产品/招商银行闪电贷/_index": WikiPageMeta(
                path="贷款产品/招商银行闪电贷/_index.md",
                title="招商银行闪电贷",
                kind="source_page",
                content_hash="h2",
                source_ids=["sd"],
                hub="贷款产品/招商银行闪电贷",
            ),
            "贷款产品/招商银行闪电贷/申请条件": WikiPageMeta(
                path="贷款产品/招商银行闪电贷/申请条件.md",
                title="申请条件",
                kind="source_page",
                content_hash="h3",
                source_ids=["sd"],
                hub="贷款产品/招商银行闪电贷",
            ),
        },
    )
    tree = build_wiki_tree(wiki)
    hub_names = [h["name"] for h in tree["hubs"]]
    assert "贷款产品/招商银行闪电贷" not in hub_names
    loan = next(h for h in tree["hubs"] if h["name"] == "贷款产品")
    assert loan["pages"][0]["page_id"] == "贷款产品/工行融e借"
    group = next(g for g in loan["groups"] if g["name"] == "招商银行闪电贷")
    assert {p["page_id"] for p in group["pages"]} == {
        "贷款产品/招商银行闪电贷/_index",
        "贷款产品/招商银行闪电贷/申请条件",
    }


def test_build_tree_includes_hub_that_only_has_index_page(tmp_path: Path):
    """product_bundle / catalog hubs whose only page is ``_index.md`` must still appear."""
    from akos.application.wiki.browser import build_wiki_tree

    wiki = tmp_path / "wiki"
    page_dir = wiki / "理财产品" / "青银理财成就系列（低波共享）"
    page_dir.mkdir(parents=True)
    (page_dir / "_index.md").write_text("# 青银理财\n\n正文\n", encoding="utf-8")
    (wiki / "index.md").write_text("# Wiki Index\n", encoding="utf-8")
    save_pages_meta(
        wiki,
        {
            "理财产品/青银理财成就系列（低波共享）/_index": WikiPageMeta(
                path="理财产品/青银理财成就系列（低波共享）/_index.md",
                title="青银理财成就系列（低波共享）",
                kind="source_page",
                content_hash="h",
                source_ids=["wealth"],
                hub="理财产品/青银理财成就系列（低波共享）",
                summary="理财产品总览",
            )
        },
    )
    tree = build_wiki_tree(wiki)
    hub = next(h for h in tree["hubs"] if h["name"] == "理财产品")
    group = next(g for g in hub["groups"] if g["name"] == "青银理财成就系列（低波共享）")
    assert group["pages"][0]["page_id"] == "理财产品/青银理财成就系列（低波共享）/_index"
    assert group["pages"][0]["title"] == "青银理财成就系列（低波共享）"


def test_read_wiki_page_works_with_relative_wiki_root(tmp_path: Path, monkeypatch: object):
    from akos.application.wiki.browser import read_wiki_page

    wiki = tmp_path / "wiki"
    (wiki / "政策").mkdir(parents=True)
    (wiki / "政策" / "保修政策.md").write_text("# 保修政策\n\n正文\n", encoding="utf-8")
    save_pages_meta(
        wiki,
        {
            "政策/保修政策": WikiPageMeta(
                path="政策/保修政策.md",
                title="保修政策",
                kind="source_page",
                content_hash="h",
                source_ids=["s1"],
                hub="政策",
            )
        },
    )
    monkeypatch.chdir(tmp_path)
    page = read_wiki_page(Path("wiki"), "政策/保修政策")
    assert page["page_id"] == "政策/保修政策"
    assert page["path"] == "政策/保修政策.md"
    assert "保修政策" in page["title"]
    assert "正文" in page["markdown"]


def test_build_tree_and_search_include_hub_index(tmp_path: Path):
    from akos.application.wiki.browser import build_wiki_tree, search_wiki_pages

    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "售后").mkdir()
    (wiki / "售后" / "_index.md").write_text("# Hub\n\n_indexneedle\n", encoding="utf-8")
    (wiki / "售后" / "叶子.md").write_text("# 叶子\n\nleafneedle\n", encoding="utf-8")
    save_pages_meta(
        wiki,
        {
            "售后/_index": WikiPageMeta(
                path="售后/_index.md",
                title="Hub",
                kind="hub_index",
                content_hash="h0",
                source_ids=[],
                hub="售后",
            ),
            "售后/叶子": WikiPageMeta(
                path="售后/叶子.md",
                title="叶子",
                kind="source_page",
                content_hash="h1",
                source_ids=["s1"],
                hub="售后",
            ),
        },
    )
    tree = build_wiki_tree(wiki)
    page_ids = [p["page_id"] for h in tree["hubs"] for p in h["pages"]]
    assert page_ids[0] == "售后/_index"
    assert "售后/叶子" in page_ids

    by_index = search_wiki_pages(wiki, "_indexneedle")
    assert by_index["total"] == 1
    assert by_index["hits"][0]["page_id"] == "售后/_index"
    by_leaf = search_wiki_pages(wiki, "leafneedle")
    assert by_leaf["total"] == 1
    assert by_leaf["hits"][0]["page_id"] == "售后/叶子"


def test_read_wiki_page_prefers_h1_when_meta_missing(tmp_path: Path):
    from akos.application.wiki.browser import read_wiki_page

    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "orphan.md").write_text("# 真实标题\n\nbody\n", encoding="utf-8")
    page = read_wiki_page(wiki, "orphan")
    assert page["title"] == "真实标题"
