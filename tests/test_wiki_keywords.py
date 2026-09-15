from retrieval.wiki_keywords import extract_keywords


def test_extract_keywords_keeps_domain_terms():
    kws = extract_keywords("电子普通发票怎么开？")
    # jieba may segment as 普通发票 (substring match intentional, not exact token)
    assert any("发票" in k for k in kws) or "电子普通发票" in kws
    assert "怎么" not in kws


def test_extract_keywords_dedupe_preserves_first_occurrence_order():
    # repeated domain term: drop later duplicates, keep first-occurrence order
    assert extract_keywords("发票发票怎么开？") == ["发票", "开"]
    assert extract_keywords("发票政策发票规则") == ["发票", "政策", "规则"]


def test_extract_keywords_empty_and_stopwords_only():
    assert extract_keywords("") == []
    assert extract_keywords("的了吗呢") == []
