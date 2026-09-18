from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path


def test_compile_wiki_root_under_data_kb():
    from akos.application.wiki.paths import compile_wiki_root

    root = compile_wiki_root("/data", "kb-1")
    assert root == Path("/data") / "kb" / "kb-1" / "wiki"


def test_compile_wiki_root_accepts_path():
    from akos.application.wiki.paths import compile_wiki_root

    root = compile_wiki_root(Path("/tmp/akos"), "demo")
    assert root == Path("/tmp/akos") / "kb" / "demo" / "wiki"


def test_pages_meta_roundtrip(tmp_path: Path):
    from akos.application.wiki.meta import WikiPageMeta, load_pages_meta, save_pages_meta
    from akos.application.wiki.paths import compile_wiki_root

    wiki_root = compile_wiki_root(tmp_path, "kb-a")
    wiki_root.mkdir(parents=True)

    updated = datetime(2026, 9, 14, 12, 0, 0, tzinfo=timezone.utc)
    pages = {
        "topic-refund": WikiPageMeta(
            path="topic-refund.md",
            title="退款",
            kind="topic",
            content_hash="abc123",
            source_ids=["src-1", "src-2"],
            updated_at=updated,
        )
    }
    save_pages_meta(wiki_root, pages)

    meta_file = wiki_root / ".meta" / "pages.json"
    assert meta_file.is_file()

    loaded = load_pages_meta(wiki_root)
    assert set(loaded) == {"topic-refund"}
    page = loaded["topic-refund"]
    assert page.path == "topic-refund.md"
    assert page.title == "退款"
    assert page.kind == "topic"
    assert page.content_hash == "abc123"
    assert page.source_ids == ["src-1", "src-2"]
    assert page.updated_at == updated
    assert page.summary is None


def test_pages_meta_persists_summary(tmp_path: Path):
    from akos.application.wiki.meta import WikiPageMeta, load_pages_meta, save_pages_meta
    from akos.application.wiki.paths import compile_wiki_root

    wiki_root = compile_wiki_root(tmp_path, "kb-b")
    wiki_root.mkdir(parents=True)
    save_pages_meta(
        wiki_root,
        {
            "商品咨询/尺码选择指南": WikiPageMeta(
                path="商品咨询/尺码选择指南.md",
                title="尺码选择指南",
                kind="source_page",
                content_hash="h1",
                source_ids=["src"],
                summary="服装与鞋码对照表及选码建议",
            )
        },
    )
    loaded = load_pages_meta(wiki_root)
    assert loaded["商品咨询/尺码选择指南"].summary == "服装与鞋码对照表及选码建议"


def test_load_pages_meta_missing_returns_empty(tmp_path: Path):
    from akos.application.wiki.meta import load_pages_meta
    from akos.application.wiki.paths import compile_wiki_root

    wiki_root = compile_wiki_root(tmp_path, "kb-empty")
    assert load_pages_meta(wiki_root) == {}
