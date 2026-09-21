from pathlib import Path

from akos.application.ingest.chunk_service import build_source_chunks
from akos.application.ingest.chunk_segmentation import merge_small_spans
from akos.application.ingest.chunker import chunk_document, estimate_token_count
from infra.settings import Settings

FLASH_LOAN_DOC = Path(__file__).resolve().parents[1] / "data" / "1e3d4f62-57f7-47fb-aa00-87a11007c7d1" / "招商银行闪电贷.md"


def test_merge_small_spans_combines_blank_line_fragments():
    text = (
        "① 闪电贷是招商银行推出的一款个人纯信用贷款产品。\n\n"
        "② 具有审批速度快、放款迅速的特点。\n\n"
        "③ 适用于个人消费、经营周转等需求。\n"
    )
    drafts = chunk_document(text, max_chars=3000, max_chunks=40, mode="general").chunks
    assert len(drafts) >= 3

    from akos.application.ingest.chunk_segmentation import StructuralSpan

    spans = [
        StructuralSpan(
            index=d.chunk_index,
            title=d.title,
            text=d.text,
            start=d.start,
            end=d.end,
            section_path=list(d.section_path),
        )
        for d in drafts
    ]
    merged = merge_small_spans(text, spans, min_tokens=50)
    assert len(merged) == 1
    assert estimate_token_count(merged[0].text) > estimate_token_count(drafts[0].text)


def test_build_source_chunks_compacts_before_return():
    text = FLASH_LOAN_DOC.read_text(encoding="utf-8")
    settings = Settings(
        chunk_index=True,
        chunk_mode="auto",
        chunk_max_chars=512,
        chunk_max_per_doc=40,
        chunk_min_tokens=50,
    )
    # Without compact, blank-line general mode hits the 40-chunk cap on this doc.
    raw = chunk_document(
        text,
        settings.chunk_max_chars,
        settings.chunk_max_per_doc,
        mode=settings.chunk_mode,
        heading_level=settings.chunk_heading_level,
    )
    assert len(raw.chunks) >= 30

    chunks, truncated = build_source_chunks("src-flash", text, settings)
    assert truncated is False
    assert 3 <= len(chunks) <= 15
    # Non-final chunks should meet the min-token budget after compact.
    assert all(c.token_count >= settings.chunk_min_tokens for c in chunks[:-1])
    # Prefer balanced sizes: no single chunk should swallow most of the doc.
    assert max(len(c.text) for c in chunks) < len(text) * 0.6
    rebuilt = "".join(c.text for c in sorted(chunks, key=lambda item: item.chunk_index))
    assert rebuilt == text
