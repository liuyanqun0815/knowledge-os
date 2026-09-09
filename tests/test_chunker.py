from __future__ import annotations

from compiler.chunker import chunk_text


def test_chunk_respects_max_chars_and_max_chunks():
    text = ("段落A\n\n" * 5) + ("X" * 5000)
    result = chunk_text(text, max_chars=1000, max_chunks=3)
    assert len(result.chunks) <= 3
    assert all(len(c) <= 1000 for c in result.chunks)
    assert result.truncated is True


def test_chunk_splits_on_blank_lines():
    text = "第一段内容\n\n第二段内容\n\n第三段内容"
    result = chunk_text(text, max_chars=3000, max_chunks=40)
    assert result.chunks == ["第一段内容", "第二段内容", "第三段内容"]
    assert result.truncated is False


def test_chunk_splits_on_markdown_headings():
    text = "# 标题一\n\n正文A\n\n## 标题二\n\n正文B"
    result = chunk_text(text, max_chars=3000, max_chunks=40)
    assert len(result.chunks) == 4
    assert result.chunks[0] == "# 标题一"
    assert result.chunks[1] == "正文A"
    assert result.chunks[2] == "## 标题二"
    assert result.chunks[3] == "正文B"
    assert result.truncated is False


def test_chunk_hard_splits_long_segment():
    text = "Y" * 2500
    result = chunk_text(text, max_chars=1000, max_chunks=40)
    assert len(result.chunks) == 3
    assert all(len(c) <= 1000 for c in result.chunks)
    assert sum(len(c) for c in result.chunks) == 2500
    assert result.truncated is False


def test_chunk_empty_text():
    result = chunk_text("", max_chars=1000, max_chunks=3)
    assert result.chunks == []
    assert result.truncated is False
