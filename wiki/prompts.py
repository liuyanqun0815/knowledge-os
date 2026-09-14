from __future__ import annotations

import json
from typing import Any


def build_topic_merge_prompt(
    *,
    topic_name: str,
    old_body: str,
    evidence: dict[str, Any] | str,
    required_wikilinks: list[str] | None = None,
) -> str:
    """Structured prompt for merging an existing topic wiki page with new evidence."""
    if isinstance(evidence, str):
        evidence_text = evidence
    else:
        evidence_text = json.dumps(evidence, ensure_ascii=False, indent=2)
    links = required_wikilinks or []
    links_block = "\n".join(f"- {link}" for link in links) if links else "- （无）"
    return f"""## 角色
你是 AKOS Wiki 主题页合并助手，负责在已有主题页上增量整理证据，而不是重写百科。

## 目标
将「旧页正文」与「本次新增/变更证据」合并为一篇主题页 Markdown，便于人读与检索。

## 规则
1. 只合并、不编造：事实必须来自旧页或证据；不得引入证据外的数字、规则或结论。
2. 保留并输出全部 required wikilink（`[[...]]`），不得删除或改写 page id。
3. 必须包含区块：摘要、要点（可含 Claim）、相关原文、相关实体、相关主题。
4. 相关原文使用 `[[source-...]]`；相关主题使用 `[[topic-...]]`；实体使用既有 `[[entity 或 主体|标签]]` 形式。
5. 可用中文叙述组织摘要与要点，但不得捏造未给出的信息。

## 输出
只输出一个 JSON 对象，不要 Markdown 代码块，不要解释：
{{"markdown": "<完整主题页 Markdown 正文>"}}

## 上下文
topic_name: {topic_name}

required_wikilinks:
{links_block}

old_body:
{old_body}

evidence:
{evidence_text}
"""
