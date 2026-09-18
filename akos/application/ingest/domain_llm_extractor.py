from __future__ import annotations

import json
import logging
import re
from typing import Protocol

from akos.application.ingest.extraction_spec import LlmExtractionSpec
from akos.domain.ports.compiler import ExtractedClaim
from akos.application.ingest.subject_bind import (
    bind_enabled,
    bind_generic_subject,
    effective_subject_bind_mode,
    subject_bind_prompt_rules,
)
from akos.adapters.llm.client import LlmConfigError
from infra.settings import get_settings

logger = logging.getLogger(__name__)


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
Subject selection (priority high → low):
1. Prefer a concrete named entity in this passage (specific product / company / policy name).
2. If the natural subject is a generic/deictic reference to THIS document
   (examples — not exhaustive: 本产品、本理财计划、本理财产品、本计划、投资者、客户、托管人、管理人,
   or 「本…产品/计划」+角色 such as 本理财产品托管人), rewrite with document_anchor when provided:
   - 本产品 / 本理财计划 / 本理财产品 → document_anchor
   - 投资者 / 客户 → {{document_anchor}}的投资者
   - 本理财产品托管人 → {{document_anchor}}的托管人
   Apply the same pattern to similar deictic subjects; do not leave bare 本产品/投资者 as subject.
3. Only if this passage has no usable subject, fall back to document_anchor alone.
4. Never let document_anchor override a different concrete product/company already named in this passage.
5. subject 禁止单独使用属性词（如「利率」「额度」「还款方式」「收入要求」）；属性写入 predicate，取值写入 object.
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
        except Exception:
            logger.exception("LLM claim extraction request failed")
            raise
        claims = self._parse_response(content, text)
        mode = effective_subject_bind_mode(get_settings().subject_bind_mode)
        if bind_enabled(mode) and document_anchor:
            rebound: list[ExtractedClaim] = []
            for claim in claims:
                new_subject = bind_generic_subject(claim.subject, document_anchor)
                if new_subject == claim.subject:
                    rebound.append(claim)
                else:
                    rebound.append(
                        ExtractedClaim(
                            subject=new_subject,
                            predicate=claim.predicate,
                            object=claim.object,
                            confidence=claim.confidence,
                            quote=claim.quote,
                            start=claim.start,
                            end=claim.end,
                        )
                    )
            return rebound
        return claims

    def _build_prompt(self, text: str, *, document_anchor: str | None = None) -> str:
        mode = effective_subject_bind_mode(get_settings().subject_bind_mode)
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
            if bind_enabled(mode):
                configuration["subject_bind_mode"] = mode
                configuration["subject_priority"] = [
                    "concrete_passage_entity",
                    "bind_generic_deixis_to_document_anchor",
                    "document_anchor",
                ]
                configuration["rules"] = list(configuration.get("rules") or []) + subject_bind_prompt_rules(
                    document_anchor
                )
            else:
                configuration["subject_priority"] = [
                    "passage_entity",
                    "document_anchor",
                ]
                configuration["rules"] = list(configuration.get("rules") or []) + [
                    "subject 优先取本段文段实体，其次才用 document_anchor",
                ]
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
        try:
            confidence = float(item.get("confidence", 0.0))
        except (TypeError, ValueError):
            confidence = 0.0
        start = text.find(quote) if quote else -1
        end = start + len(quote) if start >= 0 else -1
        return ExtractedClaim(
            subject=subject,
            predicate=predicate,
            object=obj,
            confidence=confidence,
            quote=quote,
            start=start,
            end=end,
        )
