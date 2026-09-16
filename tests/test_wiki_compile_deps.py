from __future__ import annotations

from infra.bootstrap import build_wiki_compile_deps
from infra.settings import Settings


def test_build_wiki_compile_deps_skips_embedder_and_reranker(monkeypatch, tmp_path):
    from infra import bootstrap as bootstrap_mod

    def boom_rerank(settings):
        raise AssertionError("create_reranker must not run for wiki compile deps")

    def boom_embed(settings):
        raise AssertionError("create_embedder must not run for wiki compile deps")

    monkeypatch.setattr(bootstrap_mod, "create_reranker", boom_rerank, raising=False)
    monkeypatch.setattr(bootstrap_mod, "create_embedder", boom_embed, raising=False)

    settings = Settings(
        _env_file=None,
        use_pg=False,
        data_root=str(tmp_path),
        wiki_compile=True,
        rerank_enabled=True,
        embedding_enabled=True,
    )
    deps = build_wiki_compile_deps("kb-wiki-only", settings)
    assert deps.knowledge is not None
    assert deps.graph is not None
    assert deps.llm_client is not None
    assert deps.wiki_retrieval is not None
