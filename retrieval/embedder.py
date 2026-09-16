from __future__ import annotations

import hashlib
import math
import os
from pathlib import Path
from typing import Protocol

from infra.settings import Settings


def configure_hf_hub(*, hf_endpoint: str = "") -> None:
    """Apply HuggingFace Hub endpoint override (e.g. https://hf-mirror.com)."""
    endpoint = hf_endpoint.strip().rstrip("/")
    if endpoint:
        os.environ["HF_ENDPOINT"] = endpoint


def _modelscope_snapshot_candidates(model_id: str, cache_dir: str | Path, *, revision: str = "master") -> list[Path]:
    org_name = model_id.strip().replace("/", "--")
    if not org_name:
        return []
    cache_path = Path(cache_dir).expanduser().resolve()
    return [
        cache_path / "models" / org_name / "snapshots" / revision,
        cache_path / org_name / "snapshots" / revision,
    ]


def _is_complete_modelscope_snapshot(path: Path) -> bool:
    if not path.is_dir() or not (path / "config.json").is_file():
        return False
    has_weights = (
        (path / "pytorch_model.bin").is_file()
        or (path / "model.safetensors").is_file()
        or any(path.glob("pytorch_model*.bin"))
        or any(path.glob("*.safetensors"))
    )
    has_tokenizer = (
        (path / "tokenizer.json").is_file()
        or (path / "tokenizer_config.json").is_file()
        or (path / "sentencepiece.bpe.model").is_file()
        or (path / "vocab.txt").is_file()
    )
    return has_weights and has_tokenizer


def find_local_modelscope_snapshot(
    model_id: str,
    cache_dir: str | Path,
    *,
    revision: str = "master",
) -> Path | None:
    """Return an existing ModelScope snapshot dir under cache_dir, if complete."""
    for candidate in _modelscope_snapshot_candidates(model_id, cache_dir, revision=revision):
        if _is_complete_modelscope_snapshot(candidate):
            return candidate
    return None


def resolve_modelscope_model_dir(model_id: str, cache_dir: str) -> str:
    """Download or reuse a ModelScope model directory for sentence-transformers.

    If ``cache_dir`` already contains a complete snapshot for ``model_id``, skip
    ``snapshot_download`` (avoids ModelScope hub re-validation latency).
    """
    existing = find_local_modelscope_snapshot(model_id, cache_dir)
    if existing is not None:
        return str(existing)

    try:
        from modelscope import snapshot_download
    except ImportError as exc:
        raise RuntimeError(
            "modelscope is required for ModelScope embeddings; install with: pip install 'akos[embedding]'"
        ) from exc

    cache_path = Path(cache_dir)
    cache_path.mkdir(parents=True, exist_ok=True)
    return snapshot_download(model_id, cache_dir=str(cache_path.resolve()), revision="master")


def resolve_embedding_model_path(settings: Settings) -> str:
    model_name = settings.embedding_model.strip()
    local_path = Path(model_name)
    if local_path.exists():
        return str(local_path.resolve())

    source = settings.embedding_model_source.lower()
    if source == "modelscope":
        return resolve_modelscope_model_dir(model_name, settings.embedding_cache_dir)
    return model_name


class EmbedderPort(Protocol):
    @property
    def dims(self) -> int: ...

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class HashEmbedder:
    """Deterministic pseudo-embedding for tests (no model download)."""

    def __init__(self, *, dims: int = 768) -> None:
        self._dims = dims

    @property
    def dims(self) -> int:
        return self._dims

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [_hash_to_vector(text, self._dims) for text in texts]


class SentenceTransformerEmbedder:
    """Local embedding via sentence-transformers (ModelScope dir or HuggingFace id)."""

    def __init__(self, model_name: str, *, device: str = "cpu", hf_endpoint: str = "") -> None:
        configure_hf_hub(hf_endpoint=hf_endpoint)
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError(
                "sentence-transformers is required for local embeddings; "
                "install with: pip install 'akos[embedding]'"
            ) from exc
        try:
            self._model = SentenceTransformer(model_name, device=device)
        except Exception as exc:
            hint = (
                "国内推荐 AKOS_EMBEDDING_MODEL_SOURCE=modelscope + "
                "AKOS_EMBEDDING_MODEL=AI-ModelScope/bge-base-zh-v1.5；"
                "或设置 HF_ENDPOINT=https://hf-mirror.com"
            )
            raise RuntimeError(f"failed to load embedding model {model_name!r}: {exc}. {hint}") from exc
        if hasattr(self._model, "get_embedding_dimension"):
            dim = self._model.get_embedding_dimension()
        else:
            dim = self._model.get_sentence_embedding_dimension()
        if dim is None:
            raise RuntimeError(f"embedding model {model_name!r} has unknown dimension")
        self._dims = int(dim)

    @property
    def dims(self) -> int:
        return self._dims

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors = self._model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return [vector.tolist() for vector in vectors]


def _hash_to_vector(text: str, dims: int) -> list[float]:
    vec = [0.0] * dims
    for token in _tokenize(text):
        digest = hashlib.md5(token.encode()).hexdigest()
        idx = int(digest, 16) % dims
        vec[idx] += 1.0
    norm = math.sqrt(sum(value * value for value in vec))
    if norm == 0:
        return vec
    return [value / norm for value in vec]


def _tokenize(text: str) -> list[str]:
    import re

    pattern = re.compile(r"[\w\u4e00-\u9fff]+")
    tokens = pattern.findall(text.lower())
    cjk_chars = [char for char in text if "\u4e00" <= char <= "\u9fff"]
    return tokens + cjk_chars


def create_embedder(settings: Settings) -> EmbedderPort | None:
    if not settings.embedding_enabled:
        return None
    provider = settings.embedding_provider.lower()
    if provider == "hash":
        return HashEmbedder(dims=settings.embedding_dims)
    if provider == "local":
        model_path = resolve_embedding_model_path(settings)
        hf_endpoint = settings.hf_endpoint if settings.embedding_model_source.lower() == "local" else ""
        return SentenceTransformerEmbedder(
            model_path,
            device=settings.embedding_device,
            hf_endpoint=hf_endpoint,
        )
    raise ValueError(f"unsupported embedding provider: {settings.embedding_provider}")


def claim_embedding_text(subject: str, predicate: str, object_value: str) -> str:
    return f"{subject} {predicate} {object_value}".strip()
