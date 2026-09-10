from compiler.chunker import chunk_document, validate_chunk_coverage


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
