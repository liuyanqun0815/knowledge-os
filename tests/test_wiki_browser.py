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
