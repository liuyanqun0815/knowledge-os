from __future__ import annotations

import logging
import math
import re
from dataclasses import replace
from pathlib import Path
from typing import Any, Protocol

from infra.settings import Settings
from retrieval.embedder import configure_hf_hub, resolve_modelscope_model_dir
from retrieval.fusion import normalize_hit_scores
from retrieval.ports import Hit

_TOKEN_PATTERN = re.compile(r"[\w\u4e00-\u9fff]+")
_LOG = logging.getLogger(__name__)


class RerankerPort(Protocol):
    def score_pairs(self, pairs: list[tuple[str, str]]) -> list[float]: ...


class HashReranker:
    """Deterministic overlap scorer for tests (no model download)."""

    def score_pairs(self, pairs: list[tuple[str, str]]) -> list[float]:
        scores: list[float] = []
        for query, passage in pairs:
            query_tokens = set(_tokenize(query))
            passage_tokens = set(_tokenize(passage))
            if not query_tokens or not passage_tokens:
                scores.append(0.0)
                continue
            overlap = len(query_tokens & passage_tokens)
            score = overlap / len(query_tokens)
            if query and query in passage:
                score = max(score, 1.0)
            scores.append(score)
        return scores


class _TransformersPairScorer:
    """Fallback scorer when sentence-transformers CrossEncoder cannot load the model."""

    def __init__(self, model_path: str, *, device: str = "cpu", max_length: int = 512) -> None:
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        self._torch = torch
        self._tokenizer = AutoTokenizer.from_pretrained(model_path)
        self._model = AutoModelForSequenceClassification.from_pretrained(model_path)
        self._model.to(device)
        self._model.eval()
        self._device = device
        self._max_length = max_length

    def predict(self, pairs: list[tuple[str, str]]) -> list[float]:
        if not pairs:
            return []
        encoded = self._tokenizer(
            [query for query, _ in pairs],
            [passage for _, passage in pairs],
            padding=True,
            truncation=True,
            max_length=self._max_length,
            return_tensors="pt",
        )
        encoded = {key: value.to(self._device) for key, value in encoded.items()}
        with self._torch.no_grad():
            logits = self._model(**encoded).logits.view(-1)
            scores = self._torch.sigmoid(logits)
        return [float(score) for score in scores]


class BceCrossEncoderReranker:
    """Local reranker via sentence-transformers CrossEncoder (bce-reranker-base_v1)."""

    def __init__(self, model_path: str, *, device: str = "cpu", max_length: int = 512, hf_endpoint: str = "") -> None:
        configure_hf_hub(hf_endpoint=hf_endpoint)
        self._model = self._load_model(model_path, device=device, max_length=max_length)

    @staticmethod
    def _load_model(model_path: str, *, device: str, max_length: int) -> Any:
        cross_encoder_error: Exception | None = None
        try:
            from sentence_transformers import CrossEncoder

            kwargs: dict[str, Any] = {"max_length": max_length, "device": device}
            if Path(model_path).exists():
                kwargs["local_files_only"] = True
            return CrossEncoder(model_path, **kwargs)
        except Exception as exc:
            cross_encoder_error = exc
            _LOG.warning(
                "sentence-transformers CrossEncoder failed for %s (%s); falling back to transformers",
                model_path,
                exc,
            )

        try:
            return _TransformersPairScorer(model_path, device=device, max_length=max_length)
        except Exception as exc:
            hint = (
                "国内推荐 AKOS_RERANK_MODEL_SOURCE=modelscope + "
                "AKOS_RERANK_MODEL=maidalun/bce-reranker-base_v1；"
                "或设置 HF_ENDPOINT=https://hf-mirror.com；"
                "临时可设 AKOS_RERANK_ENABLED=false"
            )
            detail = f"{exc}"
            if cross_encoder_error is not None:
                detail = f"cross_encoder={cross_encoder_error}; transformers={exc}"
            raise RuntimeError(f"failed to load rerank model {model_path!r}: {detail}. {hint}") from exc

    def score_pairs(self, pairs: list[tuple[str, str]]) -> list[float]:
        if not pairs:
            return []
        if isinstance(self._model, _TransformersPairScorer):
            return self._model.predict(list(pairs))
        raw_scores = self._model.predict(list(pairs), show_progress_bar=False)
        return to_unit_interval([float(score) for score in raw_scores])


def to_unit_interval(scores: list[float]) -> list[float]:
    """Ensure scores lie in ``[0, 1]``; apply sigmoid when values look like logits."""
    if not scores:
        return scores
    if any(score < 0.0 or score > 1.0 for score in scores):
        return [1.0 / (1.0 + math.exp(-float(score))) for score in scores]
    return [float(score) for score in scores]


def _tokenize(text: str) -> list[str]:
    tokens = _TOKEN_PATTERN.findall(text.lower())
    cjk_chars = [char for char in text if "\u4e00" <= char <= "\u9fff"]
    return tokens + cjk_chars


def resolve_rerank_model_path(settings: Settings) -> str:
    model_name = settings.rerank_model.strip()
    local_path = Path(model_name)
    if local_path.exists():
        return str(local_path.resolve())

    source = settings.rerank_model_source.lower()
    if source == "modelscope":
        return resolve_modelscope_model_dir(model_name, settings.rerank_cache_dir)
    return model_name


def create_reranker(settings: Settings) -> RerankerPort | None:
    if not settings.rerank_enabled:
        return None
    provider = settings.rerank_provider.lower()
    if provider == "hash":
        return HashReranker()
    if provider == "bce":
        model_path = resolve_rerank_model_path(settings)
        hf_endpoint = settings.hf_endpoint if settings.rerank_model_source.lower() == "local" else ""
        try:
            return BceCrossEncoderReranker(
                model_path,
                device=settings.rerank_device,
                max_length=settings.rerank_max_length,
                hf_endpoint=hf_endpoint,
            )
        except Exception as exc:
            # Wiki compile / Ask bootstrap must not hard-fail when rerank weights are incomplete.
            _LOG.warning("rerank disabled after load failure: %s", exc)
            return None
    raise ValueError(f"unsupported rerank provider: {settings.rerank_provider}")


def passage_for_hit(hit: Hit, knowledge: Any | None = None, *, max_chars: int = 400) -> str:
    """Build a short passage for cross-encoder scoring.

    Prefer title + summary for chunks (cheaper on CPU than full body text).
    """
    if hit.hit_type == "chunk" and hit.chunk_id and knowledge is not None:
        chunk = knowledge.get_chunk(hit.chunk_id)
        if chunk is not None:
            title = (chunk.title or "").strip()
            summary = (chunk.summary or "").strip()
            if title or summary:
                return f"{title} {summary}".strip()[:max_chars]
            text = (chunk.text or "").strip()
            if text:
                return text[:max_chars]

    if hit.hit_type == "wiki":
        title = hit.title or ""
        snippet = hit.snippet or ""
        passage = f"{title} {snippet}".strip()
        if passage:
            return passage[:max_chars]

    if hit.claim_id and knowledge is not None:
        claim = knowledge.get_claim(hit.claim_id)
        if claim is not None:
            return f"{claim.subject} {claim.predicate} {claim.object}".strip()[:max_chars]

    return (hit.snippet or "").strip()[:max_chars]


def rerank_hits(
    question: str,
    hits: list[Hit],
    reranker: RerankerPort,
    settings: Settings,
    *,
    knowledge: Any | None = None,
) -> list[Hit]:
    """Re-score fused hits with a cross-encoder and return top-k by relevance."""
    query = question.strip()
    if not query or not hits:
        return hits

    top_n = min(max(settings.rerank_top_n, 1), len(hits))
    candidates = hits[:top_n]
    pairs = [(query, passage_for_hit(hit, knowledge)) for hit in candidates]
    scores = to_unit_interval(reranker.score_pairs(pairs))
    ranked = sorted(zip(candidates, scores), key=lambda item: item[1], reverse=True)

    min_score = settings.rerank_min_score
    reranked: list[Hit] = []
    for hit, score in ranked:
        if min_score > 0 and score < min_score:
            continue
        reranked.append(replace(hit, score=float(score)))

    top_k = max(settings.retrieval_top_k, 1)
    if not reranked:
        return normalize_hit_scores(hits[:top_k])
    return normalize_hit_scores(reranked[:top_k])


def _is_content_hit(hit: Hit) -> bool:
    return hit.hit_type in {"chunk", "wiki"}


def rerank_content_hits_preserving_claims(
    question: str,
    hits: list[Hit],
    reranker: RerankerPort,
    settings: Settings,
    *,
    knowledge: Any | None = None,
) -> list[Hit]:
    """Rerank chunk/wiki; keep claims ahead; score everyone onto ``[0, 1]``."""
    claim_hits = [hit for hit in hits if not _is_content_hit(hit)]
    content_hits = [hit for hit in hits if _is_content_hit(hit)]
    query = question.strip()
    if not content_hits:
        if not claim_hits or not query:
            return claim_hits
        pairs = [(query, passage_for_hit(hit, knowledge)) for hit in claim_hits]
        scores = to_unit_interval(reranker.score_pairs(pairs))
        scored_claims = [replace(hit, score=float(score)) for hit, score in zip(claim_hits, scores)]
        return normalize_hit_scores(scored_claims)

    scored_claims = claim_hits
    if claim_hits and query:
        claim_pairs = [(query, passage_for_hit(hit, knowledge)) for hit in claim_hits]
        claim_scores = to_unit_interval(reranker.score_pairs(claim_pairs))
        scored_claims = [replace(hit, score=float(score)) for hit, score in zip(claim_hits, claim_scores)]

    reranked_content = rerank_hits(
        question,
        content_hits,
        reranker,
        settings,
        knowledge=knowledge,
    )
    return normalize_hit_scores(scored_claims + reranked_content)
