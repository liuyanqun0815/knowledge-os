from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from akos.domain.models.knowledge import Claim, Source, SourceChunk


class WikiLlmSummarizer:
    def __init__(
        self,
        llm_client,
        *,
        cache_dir: Path | None = None,
        prompt_version: str = "v1",
        use_cache: bool = True,
    ) -> None:
        self._client = llm_client
        self._cache_dir = cache_dir
        self._prompt_version = prompt_version
        self._use_cache = use_cache

    def _cache_key(self, payload: str) -> str:
        raw = f"{self._prompt_version}:{payload}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def _read_cache(self, key: str) -> str | None:
        if not self._use_cache or self._cache_dir is None:
            return None
        path = self._cache_dir / f"{key}.txt"
        if not path.exists():
            return None
        return path.read_text(encoding="utf-8").strip()

    def _write_cache(self, key: str, summary: str) -> None:
        if not self._use_cache or self._cache_dir is None:
            return
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        (self._cache_dir / f"{key}.txt").write_text(summary, encoding="utf-8")

    def _summarize(self, prompt: str) -> str | None:
        cache_key = self._cache_key(prompt)
        cached = self._read_cache(cache_key)
        if cached:
            return cached
        try:
            raw = self._client.chat_completions([{"role": "user", "content": prompt}], temperature=0.2)
            payload = json.loads(raw)
        except Exception:
            return None
        summary = payload.get("summary") if isinstance(payload, dict) else None
        if not isinstance(summary, str) or not summary.strip():
            return None
        summary = summary.strip()
        self._write_cache(cache_key, summary)
        return summary

    def summarize_source(self, source: Source, claims: list[Claim], chunks: list[SourceChunk]) -> str | None:
        prompt = (
            "你是 Wiki 摘要助手。根据 source 元数据、claims 与 chunks 生成中文摘要。\n"
            '只输出 JSON：{"summary":"..."}\n'
            f"source: {json.dumps({'id': source.id, 'title': source.title, 'type': source.type}, ensure_ascii=False)}\n"
            f"claims: {json.dumps([{'subject': c.subject, 'predicate': c.predicate, 'object': c.object} for c in claims[:20]], ensure_ascii=False)}\n"
            f"chunks: {json.dumps([{'title': c.title, 'summary': c.summary, 'excerpt': c.text[:200]} for c in chunks[:10]], ensure_ascii=False)}"
        )
        return self._summarize(prompt)

    def summarize_entity(
        self,
        subject: str,
        claims: list[Claim],
        related_chunks: list[SourceChunk],
    ) -> str | None:
        prompt = (
            "你是 Wiki 摘要助手。根据实体 claims 与相关 chunk 生成中文摘要。\n"
            '只输出 JSON：{"summary":"..."}\n'
            f"entity: {subject}\n"
            f"claims: {json.dumps([{'predicate': c.predicate, 'object': c.object, 'source_ids': c.source_ids} for c in claims[:20]], ensure_ascii=False)}\n"
            f"chunks: {json.dumps([{'source_id': c.source_id, 'title': c.title, 'summary': c.summary} for c in related_chunks[:10]], ensure_ascii=False)}"
        )
        return self._summarize(prompt)
