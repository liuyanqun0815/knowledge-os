from __future__ import annotations

import json
import re

from compiler.ports import ExtractedClaim, ExtractorPort
from infra.llm import LlmConfigError, OpenAiCompatibleClient

_EXTRACTION_PROMPT = """Extract knowledge claims from the following corporate culture text.
Return a JSON array of objects with keys: subject, predicate, object, confidence, quote.
Allowed predicates: 倡导, 禁止, 适用于
Entity types: Value, Behavior, Policy, Department

Text:
{text}
"""


def _find_span(text: str, quote: str) -> tuple[int, int, str]:
    if not quote:
        return 0, 0, ""
    idx = text.find(quote)
    if idx >= 0:
        return idx, idx + len(quote), quote
    return 0, min(len(text), max(len(quote), 1)), quote[: max(len(text), 1)]


def _strip_json_fence(content: str) -> str:
    stripped = content.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    return stripped.strip()


class LlmExtractor:
    """LLM-backed extractor skeleton; Phase 2.1 enables corporate_culture optionally."""

    def __init__(
        self,
        client: OpenAiCompatibleClient | None = None,
        domain: str = "corporate_culture",
    ) -> None:
        self._client = client or OpenAiCompatibleClient()
        self._domain = domain

    def extract(self, text: str) -> list[ExtractedClaim]:
        if self._domain != "corporate_culture":
            return []
        if not self._client.is_configured:
            return []

        try:
            content = self._client.chat_completions(
                [{"role": "user", "content": _EXTRACTION_PROMPT.format(text=text)}]
            )
        except LlmConfigError:
            return []

        return self._parse_response(content, text)

    def _parse_response(self, content: str, text: str) -> list[ExtractedClaim]:
        try:
            payload = json.loads(_strip_json_fence(content))
        except json.JSONDecodeError:
            return []
        if not isinstance(payload, list):
            return []

        claims: list[ExtractedClaim] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            subject = str(item.get("subject", "")).strip()
            predicate = str(item.get("predicate", "")).strip()
            obj = str(item.get("object", "")).strip()
            if not subject or not predicate or not obj:
                continue
            quote = str(item.get("quote", "")).strip() or f"{subject}{predicate}{obj}"
            confidence_raw = item.get("confidence", 0.7)
            try:
                confidence = float(confidence_raw)
            except (TypeError, ValueError):
                confidence = 0.7
            start, end, quote = _find_span(text, quote)
            claims.append(
                ExtractedClaim(
                    subject=subject,
                    predicate=predicate,
                    object=obj,
                    confidence=confidence,
                    quote=quote,
                    start=start,
                    end=end,
                )
            )
        return claims


def create_corporate_extractor(client: OpenAiCompatibleClient | None = None) -> ExtractorPort:
    """Corporate culture extractor: LLM when configured, otherwise skip (no claims)."""
    return LlmExtractor(client=client, domain="corporate_culture")
