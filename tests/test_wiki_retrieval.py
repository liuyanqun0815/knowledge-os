from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from wiki.paths import compile_wiki_root


def _write_page(wiki_root: Path, rel: str, title: str, body: str, related: list[str] | None = None) -> None:
    path = wiki_root / f"{rel}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "---",
        "type: source_page",
        "---",
        "",
        f"# {title}",
        "",
        "## 摘要",
        body,
        "",
    ]
    if related:
        lines.append("## 相关主题")
        for item in related:
            lines.append(f"- [[{item}|{item.split('/')[-1]}]]")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_index(wiki_root: Path, entries: list[tuple[str, str, str]]) -> None:
    # entries: (path_no_md, title, blurb)
    lines = ["---", "type: index", "---", "", "# Wiki Index", "", "## 主题", ""]
    for path, title, blurb in entries:
        lines.append(f"- [[{path}|{title}]] — {blurb}")
    (wiki_root / "index.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_search_skips_without_index(tmp_path: Path):
    from retrieval.wiki_index import WikiPageRetrieval

    wiki_root = compile_wiki_root(tmp_path, "kb-wiki")
    wiki_root.mkdir(parents=True)
    _write_page(wiki_root, "政策/发票政策", "发票政策", "电子发票说明")
    llm = MagicMock()
    llm.is_configured = True
    retrieval = WikiPageRetrieval(llm_client=llm)
    retrieval.index_wiki_root(wiki_root)
    assert retrieval.search("发票") == []
    llm.chat_completions.assert_not_called()


def test_search_skips_without_leaf_pages(tmp_path: Path):
    from retrieval.wiki_index import WikiPageRetrieval

    wiki_root = compile_wiki_root(tmp_path, "kb-wiki")
    wiki_root.mkdir(parents=True)
    (wiki_root / "index.md").write_text("# empty\n", encoding="utf-8")
    retrieval = WikiPageRetrieval()
    retrieval.index_wiki_root(wiki_root)
    assert retrieval.search("发票") == []


def test_search_skips_without_wiki_root():
    from retrieval.wiki_index import WikiPageRetrieval

    retrieval = WikiPageRetrieval()
    assert retrieval.search("发票") == []


def test_search_index_seed_hit(tmp_path: Path):
    from retrieval.wiki_index import WikiPageRetrieval

    wiki_root = compile_wiki_root(tmp_path, "kb-wiki")
    wiki_root.mkdir(parents=True)
    _write_page(wiki_root, "政策/发票政策", "发票政策", "默认开具电子普通发票")
    _write_page(wiki_root, "物流/发货时效说明", "发货时效说明", "付款后48小时内发货")
    _write_index(
        wiki_root,
        [
            ("政策/发票政策", "发票政策", "电子普通发票与增值税专用发票说明"),
            ("物流/发货时效说明", "发货时效说明", "现货发货时效"),
        ],
    )
    retrieval = WikiPageRetrieval()
    retrieval.index_wiki_root(wiki_root)
    hits = retrieval.search("电子发票怎么开", top_k=5)
    assert hits
    assert hits[0].hit_type == "wiki"
    assert hits[0].ref_id == "政策/发票政策"
    assert hits[0].path == "政策/发票政策.md"
    assert hits[0].title == "发票政策"
    assert all(h.path != "index.md" for h in hits)


def test_search_title_outweighs_body_only(tmp_path: Path):
    from retrieval.wiki_index import WikiPageRetrieval

    wiki_root = compile_wiki_root(tmp_path, "kb-wiki")
    wiki_root.mkdir(parents=True)
    _write_page(wiki_root, "政策/包邮政策", "包邮政策", "普通说明不含特殊词")
    _write_page(wiki_root, "规则/其它", "其它", "正文多次提到包邮包邮包邮")
    _write_index(
        wiki_root,
        [
            ("政策/包邮政策", "包邮政策", "包邮规则"),
            ("规则/其它", "其它", "包邮相关"),
        ],
    )
    retrieval = WikiPageRetrieval()
    retrieval.index_wiki_root(wiki_root)
    hits = retrieval.search("包邮", top_k=5)
    assert hits
    assert hits[0].ref_id == "政策/包邮政策"
    assert len(hits) >= 2
    assert hits[0].score > hits[1].score


def test_one_hop_keeps_real_pages_drops_entities(tmp_path: Path):
    from retrieval.wiki_index import WikiPageRetrieval

    wiki_root = compile_wiki_root(tmp_path, "kb-wiki")
    wiki_root.mkdir(parents=True)
    _write_page(
        wiki_root,
        "政策/发票政策",
        "发票政策",
        "发票说明\n\n## 相关实体\n- [[电子普通发票|电子普通发票]]\n",
        related=["政策/运费政策", "source-政策__发票"],
    )
    _write_page(wiki_root, "政策/运费政策", "运费政策", "运费与普通发票无关的邻居页")
    _write_index(
        wiki_root,
        [("政策/发票政策", "发票政策", "电子普通发票开具说明")],
    )
    retrieval = WikiPageRetrieval()
    retrieval.index_wiki_root(wiki_root)
    hits = retrieval.search("电子普通发票", top_k=5)
    ref_ids = {h.ref_id for h in hits}
    assert "政策/发票政策" in ref_ids
    assert "政策/运费政策" in ref_ids
    assert all(not (rid or "").startswith("source-") for rid in ref_ids)
    assert "电子普通发票" not in ref_ids


def test_full_scan_when_index_misses_keywords(tmp_path: Path):
    from retrieval.wiki_index import WikiPageRetrieval

    wiki_root = compile_wiki_root(tmp_path, "kb-wiki")
    wiki_root.mkdir(parents=True)
    _write_page(wiki_root, "政策/发票政策", "发票政策", "正文含有稀有词夸克发票")
    _write_page(
        wiki_root,
        "物流/发货时效说明",
        "发货时效说明",
        "无关内容",
        related=["政策/发票政策"],
    )
    _write_index(
        wiki_root,
        [
            ("政策/发票政策", "发票政策", "电子普通发票"),
            ("物流/发货时效说明", "发货时效说明", "发货时效"),
        ],
    )
    retrieval = WikiPageRetrieval()
    retrieval.index_wiki_root(wiki_root)
    hits = retrieval.search("夸克发票", top_k=5)
    assert hits
    assert hits[0].ref_id == "政策/发票政策"
    assert {h.ref_id for h in hits} == {"政策/发票政策"}
