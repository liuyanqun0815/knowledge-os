from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from wiki.meta import WikiPageMeta, save_pages_meta
from wiki.paths import compile_wiki_root


def _write_topic_page(wiki_root: Path, filename: str, title: str, body: str) -> Path:
    path = wiki_root / filename
    path.write_text(
        "\n".join(
            [
                "---",
                "tags: [topic]",
                "type: topic",
                "kb_id: kb-wiki",
                "---",
                "",
                f"# {title}",
                "",
                "## 摘要",
                f"> {body}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return path


def test_wiki_page_retrieval_indexes_topic_pages_and_searches(tmp_path: Path):
    from retrieval.wiki_index import WikiPageRetrieval

    wiki_root = compile_wiki_root(tmp_path, "kb-wiki")
    wiki_root.mkdir(parents=True)
    _write_topic_page(
        wiki_root,
        "topic-refund.md",
        "退款",
        "买家申请退款后需在 7 日内完成审核并原路退回。",
    )
    _write_topic_page(
        wiki_root,
        "topic-shipping.md",
        "发货",
        "普通订单 48 小时内发出，偏远地区除外。",
    )
    save_pages_meta(
        wiki_root,
        {
            "topic-refund": WikiPageMeta(
                path="topic-refund.md",
                title="退款",
                kind="topic",
                content_hash="h1",
                source_ids=["s1"],
                updated_at=datetime(2026, 9, 14, tzinfo=timezone.utc),
            ),
            "topic-shipping": WikiPageMeta(
                path="topic-shipping.md",
                title="发货",
                kind="topic",
                content_hash="h2",
                source_ids=["s2"],
                updated_at=datetime(2026, 9, 14, tzinfo=timezone.utc),
            ),
        },
    )

    retrieval = WikiPageRetrieval()
    retrieval.index_wiki_root(wiki_root)
    hits = retrieval.search("退款审核原路退回", top_k=3)

    assert hits
    top = hits[0]
    assert top.hit_type == "wiki"
    assert getattr(top, "ref_type", top.hit_type) == "wiki"
    assert top.ref_id == "topic-refund"
    assert top.title == "退款"
    assert top.path == "topic-refund.md"
    assert top.snippet
    assert "退款" in top.snippet or "审核" in top.snippet


def test_wiki_page_retrieval_respects_top_k(tmp_path: Path):
    from retrieval.wiki_index import WikiPageRetrieval

    wiki_root = compile_wiki_root(tmp_path, "kb-wiki")
    wiki_root.mkdir(parents=True)
    pages = (
        ("topic-a.md", "政策A", "节假日发货顺延处理规则说明"),
        ("topic-b.md", "政策B", "节假日客服值班与发货顺延"),
        ("topic-c.md", "政策C", "无关的库存盘点流程"),
    )
    meta: dict[str, WikiPageMeta] = {}
    for name, title, body in pages:
        _write_topic_page(wiki_root, name, title, body)
        page_id = name.removesuffix(".md")
        meta[page_id] = WikiPageMeta(
            path=name,
            title=title,
            kind="topic",
            content_hash=page_id,
            source_ids=[],
            updated_at=None,
        )
    save_pages_meta(wiki_root, meta)

    retrieval = WikiPageRetrieval()
    retrieval.index_wiki_root(wiki_root)
    hits = retrieval.search("节假日发货顺延", top_k=1)
    assert len(hits) == 1
    assert hits[0].ref_id in {"topic-a", "topic-b"}


def test_wiki_page_retrieval_indexes_nested_hierarchy_pages(tmp_path: Path):
    """Nested hub/leaf pages (no pages.json) must be searchable via rglob."""
    from retrieval.wiki_index import WikiPageRetrieval

    wiki_root = compile_wiki_root(tmp_path, "kb-wiki")
    nested = wiki_root / "客服话术"
    nested.mkdir(parents=True)
    _write_topic_page(
        nested,
        "沟通规范.md",
        "沟通规范",
        "客服应答须礼貌清晰，禁止推诿与敷衍。",
    )
    # Non-indexable noise under .meta must be skipped
    meta_dir = wiki_root / ".meta"
    meta_dir.mkdir(parents=True)
    (meta_dir / "noise.md").write_text("# noise\n不应被索引的元数据。\n", encoding="utf-8")

    retrieval = WikiPageRetrieval()
    retrieval.index_wiki_root(wiki_root)
    hits = retrieval.search("客服应答礼貌禁止推诿", top_k=3)

    assert hits
    top = hits[0]
    assert top.hit_type == "wiki"
    assert top.path == "客服话术/沟通规范.md"
    assert "沟通规范" in (top.title or "")
    assert all(h.path != ".meta/noise.md" for h in hits)
