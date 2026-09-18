from __future__ import annotations

from akos.application.ask.nodes import _wiki_pages_from_hits
from akos.adapters.retrieval.fusion import fuse_hits
from akos.domain.ports.retrieval import Hit


def test_wiki_pages_from_hits_includes_full_content():
    body = "# 物流查询指引\n\n订单页可查物流状态。"
    pages = _wiki_pages_from_hits(
        [
            Hit(
                score=1.0,
                snippet="订单页可查物流状态。",
                hit_type="wiki",
                ref_id="物流/物流查询指引",
                title="物流查询指引",
                path="物流/物流查询指引.md",
                content=body,
            )
        ]
    )
    assert len(pages) == 1
    assert pages[0]["content"] == body
    assert pages[0]["excerpt"] == "订单页可查物流状态。"
    assert pages[0]["path"] == "物流/物流查询指引.md"


def test_fuse_hits_preserves_wiki_content():
    body = "# 发票政策\n\n全文内容"
    wiki = [
        Hit(
            score=1.0,
            snippet="全文内容",
            hit_type="wiki",
            ref_id="政策/发票政策",
            title="发票政策",
            path="政策/发票政策.md",
            content=body,
        )
    ]
    fused = fuse_hits([], [], wiki)
    assert fused[0].content == body
