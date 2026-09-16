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
4. 相关原文使用 `[[source-...]]`；相关实体使用 `[[实体页|显示名]]`（与 required_wikilinks 一致）；相关主题使用 `[[topic-...]]`。
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


def build_source_wiki_plan_prompt(
    *,
    source_id: str,
    source_title: str,
    source_text: str,
    folder: str,
    default_slug: str,
    evidence: dict[str, Any],
    old_pages: list[dict[str, str]] | None = None,
    required_wikilinks: list[str] | None = None,
    wiki_catalog: list[dict[str, str]] | None = None,
) -> str:
    """Prompt LLM to plan structured wiki page(s) from a full source document."""
    evidence_text = json.dumps(evidence, ensure_ascii=False, indent=2)
    old_block = json.dumps(old_pages or [], ensure_ascii=False, indent=2)
    catalog_block = json.dumps(wiki_catalog or [], ensure_ascii=False, indent=2)
    links = required_wikilinks or []
    links_block = "\n".join(f"- {link}" for link in links) if links else "- （无）"
    return f"""## 角色
你是 AKOS Wiki 结构化编译助手。请**完整阅读源文档**，结合已萃取的 chunks/claims，规划 Wiki 页面目录与正文。

## 目标
1. 以**源文档业务主题**聚合内容，生成结构化 Markdown 页（概要、问答、表格/要点、客服话术、关键词）。
2. **默认一源一主文件**：除非源文档内存在明显独立的大主题（如「服装保养」与「正品保障」），否则不要拆碎。
3. **禁止**为表格行、尺码码数、实体值单独建页（如「女装尺码L」「中国码36」应写入主文件的表格/问答小节）。
4. 目录 folder 优先沿用源文件所在分类；slug 为可读中文文件名（无 .md 后缀）。

## 规则
1. 只使用源文档与 evidence 中的事实，不得编造规则、数字或流程。
2. 必须保留全部 required wikilink（`[[...]]`），不得删除或改写 id。
3. 每个 page 的 markdown 必须包含：摘要、问答（predicate→object 整理为 Q&A）、**相关主题**、相关原文、相关实体（如有）、Chunks（如有）。
4. 若 old_pages 非空，在其基础上增量合并/修正，不要丢失已有正确内容。
5. 问答应覆盖该页相关的 claims；表格类 claims 可合并为 markdown 表格。
6. **相关主题**：从 wiki_catalog 挑选 3~8 个业务相关的**其他 Wiki 页**，使用 `[[folder/slug|显示名]]` 互链（如 `[[售后/七天无理由退货|七天无理由退货]]`），不要链接本页。
7. 段落内的概念/实体用普通文字描述，**不要**用 `[[实体名|实体名]]` 伪造页面链接；跨页关联只用 wiki_catalog 中的页面。

## 输出
只输出一个 JSON 对象，不要 Markdown 代码块，不要解释：
{{
  "pages": [
    {{
      "folder": "{folder}",
      "slug": "{default_slug}",
      "title": "页面标题",
      "markdown": "完整 Markdown 正文（含 frontmatter 以外的正文，需含 ## 摘要 等区块）"
    }}
  ]
}}

## 上下文
source_id: {source_id}
source_title: {source_title}
default_folder: {folder}
default_slug: {default_slug}

required_wikilinks:
{links_block}

old_pages:
{old_block}

wiki_catalog:
{catalog_block}

source_text:
{source_text}

evidence:
{evidence_text}
"""
