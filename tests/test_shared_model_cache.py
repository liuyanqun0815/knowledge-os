from __future__ import annotations

from infra import bootstrap as bootstrap_mod
from akos.bootstrap import reset_shared_model_cache
from infra.settings import Settings


def test_shared_embedder_and_reranker_loaded_once(monkeypatch):
    reset_shared_model_cache()
    calls = {"embed": 0, "rerank": 0}

    def fake_embedder(settings):
        calls["embed"] += 1
        return object()

    def fake_reranker(settings):
        calls["rerank"] += 1
        return object()

    monkeypatch.setattr(bootstrap_mod, "create_embedder", fake_embedder)
    monkeypatch.setattr(bootstrap_mod, "create_reranker", fake_reranker)

    settings = Settings(
        _env_file=None,
        use_pg=False,
        embedding_enabled=True,
        embedding_provider="hash",
        rerank_enabled=True,
        rerank_provider="hash",
    )
    first_embed = bootstrap_mod._get_shared_embedder(settings)
    second_embed = bootstrap_mod._get_shared_embedder(settings)
    first_rerank = bootstrap_mod._get_shared_reranker(settings)
    second_rerank = bootstrap_mod._get_shared_reranker(settings)

    assert first_embed is second_embed
    assert first_rerank is second_rerank
    assert calls == {"embed": 1, "rerank": 1}
    reset_shared_model_cache()
