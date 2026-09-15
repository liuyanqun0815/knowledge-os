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
