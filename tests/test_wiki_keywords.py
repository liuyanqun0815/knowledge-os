from retrieval.wiki_keywords import extract_keywords


def test_extract_keywords_keeps_domain_terms():
    kws = extract_keywords("电子普通发票怎么开？")
    assert any("发票" in k for k in kws) or "电子普通发票" in kws
    assert "怎么" not in kws


def test_extract_keywords_empty_and_stopwords_only():
    assert extract_keywords("") == []
    assert extract_keywords("的了吗呢") == []
