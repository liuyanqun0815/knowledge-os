"""Tests for wiki index descriptions."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from wiki.meta import WikiPageMeta, save_pages_meta
from wiki.source_plan import extract_page_summary, rebuild_wiki_index


def test_extract_page_summary_from_blockquote() -> None:
    markdown = "\n".join(
        [
            "# 尺码选择指南",
            "",
            "## 摘要",
            "",
            "> 本页汇总服装与鞋码对照表及选码建议。不同品牌可能有差异。",
            "",
            "## 问答",
            "- x",
        ]
    )
    summary = extract_page_summary(markdown)
    assert summary.startswith("本页汇总服装与鞋码对照表")
    assert "不同品牌" in summary


def test_rebuild_wiki_index_includes_page_and_folder_descriptions(tmp_path: Path) -> None:
    wiki_root = tmp_path / "wiki"
    (wiki_root / "售后").mkdir(parents=True)
    (wiki_root / "售后" / "七天无理由退货.md").write_text(
        "# 七天无理由退货\n\n## 摘要\n\n说明七天无理由退货的适用范围与申请流程。\n\n## Chunks\n- x\n",
        encoding="utf-8",
    )
    (wiki_root / "售后" / "退换货流程.md").write_text(
        "# 退换货流程\n\n## 摘要\n\n介绍退换货申请步骤与审核时效。\n\n## Chunks\n- x\n",
        encoding="utf-8",
    )
    pages_meta = {
        "售后/七天无理由退货": WikiPageMeta(
            path="售后/七天无理由退货.md",
            title="七天无理由退货",
            kind="source_page",
            content_hash="a",
            source_ids=["s1"],
            updated_at=datetime.now(timezone.utc),
            hub="售后",
            role="leaf",
            summary="说明七天无理由退货的适用范围与申请流程。",
        ),
        "售后/退换货流程": WikiPageMeta(
            path="售后/退换货流程.md",
            title="退换货流程",
            kind="source_page",
            content_hash="b",
            source_ids=["s2"],
            updated_at=datetime.now(timezone.utc),
            hub="售后",
            role="leaf",
            summary="介绍退换货申请步骤与审核时效。",
        ),
    }
    save_pages_meta(wiki_root, pages_meta)
    rebuild_wiki_index(wiki_root, "kb1", pages_meta)

    index_body = (wiki_root / "index.md").read_text(encoding="utf-8")
    assert "### 售后" in index_body
    assert "> 涵盖七天无理由退货、退换货流程。" in index_body
    assert "- [[售后/七天无理由退货|七天无理由退货]] — 说明七天无理由退货的适用范围与申请流程。" in index_body
    assert "- [[售后/退换货流程|退换货流程]] — 介绍退换货申请步骤与审核时效。" in index_body
