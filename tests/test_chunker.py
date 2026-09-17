from compiler.chunker import (
    chunk_document,
    detect_chunk_mode,
    validate_chunk_coverage,
)


def test_chunk_document_covers_full_text_without_gaps():
    text = "# 标题\n\n第一段说明。\n\n第二段说明。"
    result = chunk_document(text, max_chars=100, max_chunks=10)
    validate_chunk_coverage(text, result.chunks)
    assert result.chunks[0].start == 0
    assert result.chunks[-1].end == len(text)
    assert "".join(chunk.text for chunk in result.chunks) == text


def test_chunk_document_merges_overflow_instead_of_dropping_tail():
    text = "a" * 250
    result = chunk_document(text, max_chars=100, max_chunks=2)
    assert result.truncated is True
    validate_chunk_coverage(text, result.chunks)
    assert len(result.chunks) == 2
    assert result.chunks[-1].end == len(text)


def test_detect_chunk_mode_heading_when_enough_h2():
    text = "# 合集\n\n## 概述\n\nx\n\n## 产品A\n\ny\n\n## 产品B\n\nz\n"
    assert detect_chunk_mode(text) == "heading"


def test_detect_chunk_mode_general_without_headings():
    text = "这是没有标题的说明书正文。\n\n第二段。"
    assert detect_chunk_mode(text) == "general"


def test_chunk_document_heading_mode_keeps_h3_inside_h2():
    text = (
        "# 合集\n\n"
        "## 1. 个人信用贷款\n\n"
        "### 产品描述\n\n无需抵押。\n\n"
        "## 2. 房屋抵押贷款\n\n"
        "### 产品描述\n\n有抵押。\n"
    )
    result = chunk_document(text, max_chars=5000, max_chunks=20, mode="heading", heading_level=2)
    validate_chunk_coverage(text, result.chunks)
    titles = [chunk.title for chunk in result.chunks if chunk.title]
    assert "1. 个人信用贷款" in titles
    assert "2. 房屋抵押贷款" in titles
    personal = next(chunk for chunk in result.chunks if chunk.title == "1. 个人信用贷款")
    assert "### 产品描述" in personal.text
    assert "无需抵押" in personal.text
    assert "房屋抵押贷款" not in personal.text


def test_chunk_document_auto_uses_heading_for_structured_doc():
    text = "# 合集\n\n## 概述\n\n简介\n\n## 产品A\n\n内容A\n\n## 产品B\n\n内容B\n"
    result = chunk_document(text, max_chars=5000, max_chunks=20, mode="auto", heading_level=2)
    assert len([c for c in result.chunks if c.title]) >= 2
