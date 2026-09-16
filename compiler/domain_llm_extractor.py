from __future__ import annotations

import json
import re
from typing import Protocol

from compiler.extraction_spec import LlmExtractionSpec
from compiler.ports import ExtractedClaim
from infra.llm import LlmConfigError


class LlmClient(Protocol):
    @property
    def is_configured(self) -> bool: ...

    def chat_completions(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.0,
        timeout: float = 60.0,
    ) -> str: ...


_CLAIM_JSON_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "required": ["subject", "predicate", "object", "confidence", "quote"],
        "properties": {
            "subject": "string",
            "predicate": "string",
            "object": "string",
            "confidence": "number",
            "quote": "string",
        },
    },
}

_PROMPT = """Extract knowledge claims from the text.
Respond with only a JSON array matching json_schema.
Each quote must be an exact, non-empty substring of the source text.
10. subject 必须是原文中的具体产品名、政策/规则名或主题实体；禁止单独使用属性词（如「利率」「额度」「还款方式」「收入要求」）作 subject。属性写入 predicate，取值写入 object。
11. 若配置中提供 document_anchor：本段 Claim 的 subject 应使用该锚点（或原文中与之同指的产品全称/简称），不要改用泛化属性词。
Extraction configuration:
{configuration}
json_schema:
{json_schema}
Source text:
{text}
"""


def _strip_json_fence(content: str) -> str:
    stripped = content.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    return stripped.strip()


class DomainLlmExtractor:
    """Extract raw claims using domain-specific prompt configuration."""

    def __init__(self, client: LlmClient, spec: LlmExtractionSpec) -> None:
        self._client = client
        self._spec = spec

    def extract(self, text: str, *, document_anchor: str | None = None) -> list[ExtractedClaim]:
        if not self._client.is_configured:
            return []

        try:
            content = self._client.chat_completions(
                [{"role": "user", "content": self._build_prompt(text, document_anchor=document_anchor)}]
            )
        except LlmConfigError:
            return []
        return self._parse_response(content, text)

    def _build_prompt(self, text: str, *, document_anchor: str | None = None) -> str:
        if self._spec.open_predicates:
            configuration = {
                "mode": "open",
                "suggested_predicates": self._spec.allowed_predicates,
                "suggested_entity_types": self._spec.entity_types,
                "prompt_locale": self._spec.prompt_locale,
                "few_shot_hints": self._spec.few_shot_hints or [],
                "rules": [
                    "可使用最贴切的中文谓词，不必限于 suggested_predicates",
                    "quote 必须是原文连续非空子串",
                    "只输出匹配 json_schema 的 JSON 数组",
                ],
            }
        else:
            configuration = {
                "allowed_predicates": self._spec.allowed_predicates,
                "entity_types": self._spec.entity_types,
                "prompt_locale": self._spec.prompt_locale,
                "few_shot_hints": self._spec.few_shot_hints or [],
            }
        if document_anchor:
            configuration["document_anchor"] = document_anchor
        return _PROMPT.format(
            configuration=json.dumps(configuration, ensure_ascii=False),
            json_schema=json.dumps(_CLAIM_JSON_SCHEMA, ensure_ascii=False),
            text=text,
        )

    def _parse_response(self, content: str, text: str) -> list[ExtractedClaim]:
        try:
            payload = json.loads(_strip_json_fence(content))
        except json.JSONDecodeError:
            return []
        if not isinstance(payload, list):
            return []

        claims: list[ExtractedClaim] = []
        for item in payload:
            claim = self._parse_claim(item, text)
            if claim is not None:
                claims.append(claim)
        return claims

    @staticmethod
    def _parse_claim(item: object, text: str) -> ExtractedClaim | None:
        if not isinstance(item, dict):
            return None
        subject = str(item.get("subject", "")).strip()
        predicate = str(item.get("predicate", "")).strip()
        obj = str(item.get("object", "")).strip()
        if not subject or not predicate or not obj:
            return None

        quote = str(item.get("quote", "")).strip() or f"{subject}{predicate}{obj}"
        if not quote:
            return None
        # Missing quotes (start < 0) still return a claim so the compiler can
        # quarantine as span_missing rather than silently dropping here.
        start = text.find(quote)

        try:
            confidence = float(item.get("confidence", 0.7))
        except (TypeError, ValueError):
            confidence = 0.7
        return ExtractedClaim(
            subject=subject,
            predicate=predicate,
            object=obj,
            confidence=confidence,
            quote=quote,
            start=start,
            end=start + len(quote),
        )
