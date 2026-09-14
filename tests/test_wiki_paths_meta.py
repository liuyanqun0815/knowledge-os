from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path


def test_compile_wiki_root_under_data_kb():
    from wiki.paths import compile_wiki_root

    root = compile_wiki_root("/data", "kb-1")
    assert root == Path("/data") / "kb" / "kb-1" / "wiki"


def test_compile_wiki_root_accepts_path():
    from wiki.paths import compile_wiki_root

    root = compile_wiki_root(Path("/tmp/akos"), "demo")
    assert root == Path("/tmp/akos") / "kb" / "demo" / "wiki"


def test_pages_meta_roundtrip(tmp_path: Path):
    from wiki.meta import WikiPageMeta, load_pages_meta, save_pages_meta
    from wiki.paths import compile_wiki_root

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


def test_load_pages_meta_missing_returns_empty(tmp_path: Path):
    from wiki.meta import load_pages_meta
    from wiki.paths import compile_wiki_root

    wiki_root = compile_wiki_root(tmp_path, "kb-empty")
    assert load_pages_meta(wiki_root) == {}
