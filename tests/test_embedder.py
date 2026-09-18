from pathlib import Path

from akos.adapters.retrieval.embedder import HashEmbedder, claim_embedding_text, create_embedder
from infra.settings import Settings


def test_hash_embedder_returns_unit_vectors():
    embedder = HashEmbedder(dims=768)
    vectors = embedder.embed(["投诉升级 包含 找主管"])
    assert len(vectors) == 1
    assert len(vectors[0]) == 768
    norm = sum(value * value for value in vectors[0]) ** 0.5
    assert 0.99 <= norm <= 1.01


def test_create_embedder_hash_provider():
    settings = Settings(_env_file=None, embedding_enabled=True, embedding_provider="hash", embedding_dims=768)
    embedder = create_embedder(settings)
    assert embedder is not None
    assert embedder.dims == 768


def test_claim_embedding_text_joins_triple():
    assert claim_embedding_text("投诉人", "有权要求", "书面回复") == "投诉人 有权要求 书面回复"


def test_resolve_modelscope_skips_download_when_cache_complete(tmp_path, monkeypatch):
    from akos.adapters.retrieval.embedder import find_local_modelscope_snapshot, resolve_modelscope_model_dir

    model_id = "maidalun/bce-reranker-base_v1"
    snap = tmp_path / "models" / "maidalun--bce-reranker-base_v1" / "snapshots" / "master"
    snap.mkdir(parents=True)
    (snap / "config.json").write_text("{}", encoding="utf-8")
    (snap / "pytorch_model.bin").write_bytes(b"fake")
    (snap / "tokenizer_config.json").write_text("{}", encoding="utf-8")

    def boom(*args, **kwargs):
        raise AssertionError("snapshot_download must not be called when cache is complete")

    monkeypatch.setitem(
        __import__("sys").modules,
        "modelscope",
        type("M", (), {"snapshot_download": staticmethod(boom)})(),
    )

    found = find_local_modelscope_snapshot(model_id, tmp_path)
    assert found == snap.resolve()
    assert resolve_modelscope_model_dir(model_id, str(tmp_path)) == str(snap.resolve())


def test_resolve_modelscope_downloads_when_cache_incomplete(tmp_path, monkeypatch):
    from akos.adapters.retrieval.embedder import resolve_modelscope_model_dir

    model_id = "maidalun/bce-reranker-base_v1"
    snap = tmp_path / "models" / "maidalun--bce-reranker-base_v1" / "snapshots" / "master"
    snap.mkdir(parents=True)
    (snap / "config.json").write_text("{}", encoding="utf-8")
    # missing weights + tokenizer → incomplete

    calls: list[tuple] = []

    def fake_download(model_id_arg, cache_dir=None, revision="master"):
        calls.append((model_id_arg, cache_dir, revision))
        out = Path(cache_dir) / "downloaded"
        out.mkdir(parents=True, exist_ok=True)
        return str(out)

    monkeypatch.setitem(
        __import__("sys").modules,
        "modelscope",
        type("M", (), {"snapshot_download": staticmethod(fake_download)})(),
    )

    result = resolve_modelscope_model_dir(model_id, str(tmp_path))
    assert calls and calls[0][0] == model_id
    assert result.endswith("downloaded")
