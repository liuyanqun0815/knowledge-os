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
from akos.adapters.llm.client import require_llm_configured
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

_PROMPT = """# 角色
你是知识抽取助手，从业务文档中抽取可入库的知识 Claim（三元组事实）。

# 目标
阅读下方「原文」，抽取准确、可溯源的 Claim；主语尽量具体、可检索；不要编造原文没有的信息。

# 规则
## 主语选择（优先级从高到低）
1. 优先使用本段中的具体具名实体（具体产品 / 公司 / 政策名称）。
2. 若自然主语是指向「本文档」的泛指/指示语（示例非穷尽：本产品、本理财计划、本理财产品、本计划、投资者、客户、托管人、管理人，或「本…产品/计划」+角色如本理财产品托管人），在提供 `document_anchor` 时改写为：
   - 本产品 / 本理财计划 / 本理财产品 → `document_anchor`
   - 投资者 / 客户 → `{{document_anchor}}的投资者`
   - 本理财产品托管人 → `{{document_anchor}}的托管人`
   同类指示主语按同样模式处理；不要把光秃秃的「本产品」「投资者」留作 subject。
3. 仅当本段没有可用主语时，才单独回退为 `document_anchor`。
4. 切勿用 `document_anchor` 覆盖本段已点名的其他具体产品/公司。
5. subject 禁止单独使用属性词（如「利率」「额度」「还款方式」「收入要求」）；属性写入 predicate，取值写入 object。
6. 本段在讲某产品条款、但正文未反复写出产品名时，subject 使用 `document_anchor`（文档级产品名），不要用「普通单位」「优质单位」「贷款额度」「房产因素」等范畴词或属性词作 subject；这些词可写入 predicate 或 object。章节标题不是产品名，不得当作 document_anchor。

## 证据与内容
- 每条 `quote` 必须是原文中的非空精确连续子串，不得摘自章节摘要。
- 章节标题与摘要只帮助判断产品/主题，不作为 quote 来源。
- 不要编造原文未出现的事实；不确定时提高谨慎或降低 confidence。

# 输出
- 只输出符合下方 json_schema 的 **JSON 数组**，不要 Markdown 代码围栏，不要其他说明文字。
- 每项字段：`subject`、`predicate`、`object`、`confidence`、`quote`。

# 参考
## 抽取配置
{configuration}

## json_schema
{json_schema}

## 原文
章节标题与摘要仅辅助理解本段主题，不可作为 quote 来源；可抽取证据仅来自下方正文。

- 章节标题：{section_title}
- 章节摘要：{section_summary}

### 正文
{text}
"""


def _strip_json_fence(content: str) -> str:
    stripped = content.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    return stripped.strip()


class DomainLlmExtractor:
    """按领域抽取配置，用 LLM 从正文抽取原始 Claim。"""

    def __init__(self, client: LlmClient, spec: LlmExtractionSpec) -> None:
        self._client = client
        self._spec = spec

    def extract(
        self,
        text: str,
        *,
        document_anchor: str | None = None,
        section_title: str | None = None,
        section_summary: str | None = None,
    ) -> list[ExtractedClaim]:
        require_llm_configured(self._client, feature="Claim LLM 抽取")

        try:
            content = self._client.chat_completions(
                [
                    {
                        "role": "user",
                        "content": self._build_prompt(
                            text,
                            document_anchor=document_anchor,
                            section_title=section_title,
                            section_summary=section_summary,
                        ),
                    }
                ]
            )
        except Exception:
            logger.exception("LLM Claim 抽取请求失败")
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

    def _build_prompt(
        self,
        text: str,
        *,
        document_anchor: str | None = None,
        section_title: str | None = None,
        section_summary: str | None = None,
    ) -> str:
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
            section_title=(section_title or "").strip() or "（无）",
            section_summary=(section_summary or "").strip() or "（无）",
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
