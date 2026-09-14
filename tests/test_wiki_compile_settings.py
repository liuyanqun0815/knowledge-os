from __future__ import annotations


def test_wiki_compile_and_purge_settings_defaults(monkeypatch):
    monkeypatch.delenv("AKOS_PURGE_STALE_CHUNKS", raising=False)
    monkeypatch.delenv("AKOS_WIKI_COMPILE", raising=False)
    monkeypatch.delenv("AKOS_WIKI_COMPILE_LLM", raising=False)
    monkeypatch.delenv("AKOS_RETRIEVAL_CLAIM_WEIGHT", raising=False)
    monkeypatch.delenv("AKOS_RETRIEVAL_WIKI_WEIGHT", raising=False)
    monkeypatch.delenv("AKOS_RETRIEVAL_CHUNK_WEIGHT", raising=False)
    monkeypatch.delenv("AKOS_WIKI_LINK_EXPAND", raising=False)
    from infra.settings import Settings

    s = Settings(_env_file=None)
    assert s.purge_stale_chunks is True
    assert s.wiki_compile is True
    assert s.wiki_compile_llm is True
    assert s.retrieval_claim_weight == 1.0
    assert s.retrieval_wiki_weight == 0.9
    assert s.retrieval_chunk_weight == 0.8
    assert s.wiki_link_expand is False
