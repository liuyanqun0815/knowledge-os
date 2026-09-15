from pathlib import Path

from wiki.meta import WikiPageMeta, save_pages_meta


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
    from wiki.browser import resolve_wiki_page_path

    wiki = tmp_path / "wiki"
    wiki.mkdir()
    try:
        resolve_wiki_page_path(wiki, "../secrets")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_build_tree_groups_by_hub(tmp_path: Path):
    from wiki.browser import build_wiki_tree

    wiki = tmp_path / "wiki"
    _seed(wiki)
    tree = build_wiki_tree(wiki)
    hub = next(h for h in tree["hubs"] if h["name"] == "售后")
    assert hub["pages"][0]["page_id"] == "售后/七天无理由退货"


def test_search_matches_body_snippet(tmp_path: Path):
    from wiki.browser import search_wiki_pages

    wiki = tmp_path / "wiki"
    _seed(wiki)
    result = search_wiki_pages(wiki, "退款")
    assert result["total"] >= 1
    assert result["hits"][0]["page_id"] == "售后/七天无理由退货"
    assert any("退款" in s for s in result["hits"][0]["snippets"])


def test_search_empty_query(tmp_path: Path):
    from wiki.browser import search_wiki_pages

    wiki = tmp_path / "wiki"
    _seed(wiki)
    for query in ("", "   "):
        result = search_wiki_pages(wiki, query)
        assert result["total"] == 0
        assert result["hits"] == []


def test_build_tree_hub_description(tmp_path: Path):
    from wiki.browser import build_wiki_tree

    wiki = tmp_path / "wiki"
    _seed(wiki)
    tree = build_wiki_tree(wiki)
    hub = next(h for h in tree["hubs"] if h["name"] == "售后")
    assert hub["description"] == "涵盖七天无理由退货。"


def test_search_title_ranks_above_body(tmp_path: Path):
    from wiki.browser import search_wiki_pages

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
    from wiki.browser import search_wiki_pages

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
    from wiki.browser import build_wiki_tree

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
    from wiki.browser import build_wiki_tree, read_wiki_page

    wiki = tmp_path / "wiki"
    _seed(wiki)
    tree = build_wiki_tree(wiki)
    page_ids = [p["page_id"] for h in tree["hubs"] for p in h["pages"]]
    assert "index" in page_ids
    overview = next(h for h in tree["hubs"] if h["name"] == "总览")
    assert overview["pages"][0]["page_id"] == "index"
    page = read_wiki_page(wiki, "index")
    assert page["page_id"] == "index"
    assert page["path"] == "index.md"


def test_build_tree_and_search_skip_hub_index(tmp_path: Path):
    from wiki.browser import build_wiki_tree, search_wiki_pages

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
    assert "售后/_index" not in page_ids
    assert "售后/叶子" in page_ids

    by_index = search_wiki_pages(wiki, "_indexneedle")
    assert by_index["total"] == 0
    by_leaf = search_wiki_pages(wiki, "leafneedle")
    assert by_leaf["total"] == 1
    assert by_leaf["hits"][0]["page_id"] == "售后/叶子"


def test_read_wiki_page_prefers_h1_when_meta_missing(tmp_path: Path):
    from wiki.browser import read_wiki_page

    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "orphan.md").write_text("# 真实标题\n\nbody\n", encoding="utf-8")
    page = read_wiki_page(wiki, "orphan")
    assert page["title"] == "真实标题"
