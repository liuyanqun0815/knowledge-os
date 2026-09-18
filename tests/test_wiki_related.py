"""Tests for cross-page wiki related links."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from akos.application.wiki.meta import WikiPageMeta
from akos.application.wiki.related import ensure_related_topics_section, refresh_all_wiki_related_links, suggest_related_wiki_links


def _meta(path: str, title: str) -> WikiPageMeta:
    return WikiPageMeta(
        path=path,
        title=title,
        kind="source_page",
        content_hash="abc",
        source_ids=["src-a"],
        updated_at=datetime.now(timezone.utc),
        hub=Path(path).parent.as_posix(),
        role="leaf",
    )


def test_suggest_related_wiki_links_by_shared_terms() -> None:
    pages_meta = {
        "商品咨询/尺码选择指南": _meta("商品咨询/尺码选择指南.md", "尺码选择指南"),
        "售后/七天无理由退货": _meta("售后/七天无理由退货.md", "七天无理由退货"),
        "物流/发货时效说明": _meta("物流/发货时效说明.md", "发货时效说明"),
    }
    links = suggest_related_wiki_links(
        page_id="商品咨询/尺码选择指南",
        title="尺码选择指南",
        source_text="尺码不合适支持七天无理由退换货",
        pages_meta=pages_meta,
        max_related=5,
    )
    joined = "\n".join(links)
    assert "[[售后/七天无理由退货|七天无理由退货]]" in joined
    assert "发货时效说明" not in joined


def test_ensure_related_topics_section_inserts_before_chunks() -> None:
    body = "# 标题\n\n## 摘要\n\n内容\n\n## Chunks\n- x\n"
    updated = ensure_related_topics_section(body, ["[[售后/七天无理由退货|七天无理由退货]]"])
    assert "## 相关主题" in updated
    assert updated.index("## 相关主题") < updated.index("## Chunks")
    assert "[[售后/七天无理由退货|七天无理由退货]]" in updated


def test_refresh_all_wiki_related_links_updates_files(tmp_path: Path) -> None:
    wiki_root = tmp_path / "wiki"
    (wiki_root / "商品咨询").mkdir(parents=True)
    (wiki_root / "售后").mkdir(parents=True)
    (wiki_root / "商品咨询" / "尺码选择指南.md").write_text(
        "# 尺码选择指南\n\n## 摘要\n\n尺码不合适可七天无理由退货\n\n## Chunks\n- x\n",
        encoding="utf-8",
    )
    (wiki_root / "售后" / "七天无理由退货.md").write_text(
        "# 七天无理由退货\n\n## 摘要\n\n退货条件\n\n## Chunks\n- x\n",
        encoding="utf-8",
    )
    pages_meta = {
        "商品咨询/尺码选择指南": _meta("商品咨询/尺码选择指南.md", "尺码选择指南"),
        "售后/七天无理由退货": _meta("售后/七天无理由退货.md", "七天无理由退货"),
    }
    updated = refresh_all_wiki_related_links(wiki_root, pages_meta, max_related=5)
    assert updated >= 1
    size_body = (wiki_root / "商品咨询" / "尺码选择指南.md").read_text(encoding="utf-8")
    assert "## 相关主题" in size_body
    assert "[[售后/七天无理由退货|七天无理由退货]]" in size_body
