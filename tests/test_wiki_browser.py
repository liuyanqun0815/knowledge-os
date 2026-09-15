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
    assert tree["hubs"][0]["name"] == "售后"
    assert tree["hubs"][0]["pages"][0]["page_id"] == "售后/七天无理由退货"


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
    assert tree["hubs"][0]["description"] == "涵盖七天无理由退货。"


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
