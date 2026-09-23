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
3. 必须包含区块：摘要、要点、常见问题（3~8 条）、相关原文、相关实体、相关主题。
4. 相关原文使用 `[[source-...]]`；相关实体使用 `[[实体页|显示名]]`（与 required_wikilinks 一致）；相关主题使用路径型 wikilink。
5. 可用中文叙述组织摘要与要点，但不得捏造未给出的信息。
6. **禁止**把全部 claims 倾倒成问答；常见问题只保留高频 3~8 条。

## 输出
只输出一个 JSON 对象，不要 Markdown 代码块，不要解释：
{{"markdown": "<完整主题页 Markdown 正文>"}}

## 参考
topic_name: {topic_name}

required_wikilinks:
{links_block}

old_body:
{old_body}

evidence:
{evidence_text}
"""


def build_source_wiki_outline_prompt(
    *,
    source_id: str,
    source_title: str,
    source_text: str,
    folder: str,
    default_slug: str,
    evidence: dict[str, Any],
    split_mode: str = "single",
    category: str = "",
    product_name: str = "",
) -> str:
    """Ask LLM only for the page outline (no full markdown) to avoid output truncation."""
    evidence_text = json.dumps(
        {
            "chunks": [
                {
                    "chunk_index": c.get("chunk_index"),
                    "title": c.get("title"),
                    "topics": c.get("topics"),
                    "summary": c.get("summary"),
                }
                for c in (evidence.get("chunks") or [])
            ],
            "claims_sample": (evidence.get("claims") or [])[:20],
        },
        ensure_ascii=False,
        indent=2,
    )
    category_name = category or folder.split("/", 1)[0]
    product = product_name or default_slug
    if split_mode in {"product_bundle", "catalog_bundle"}:
        split_hint = (
            f"必须多页：含 slug=`_index` 总览，再按业务主题拆 3~10 个子页；"
            f"folder 固定 `{folder}`；不要机械复刻「一、二、」目录编号。"
        )
    else:
        split_hint = f"默认一页：folder=`{folder}` slug=`{default_slug}`；仅在有明显独立主题时拆页。"

    return f"""## 角色
你是 AKOS Wiki 目录规划助手。只规划页面目录，不写正文。

## 目标
{split_hint}
类目建议：`{category_name}`；产品/合集名：`{product}`。

## 规则
1. 按产品、场景或主题聚合，slug/title 用可读中文短名（如「准入与申请」「利率与费用」）。
2. 禁止为表格行、单个数字、零散实体单独建页；禁止按原文「一、二、三」章节机械拆页。
3. **互斥划分**：各子页覆盖的要点类型不得重叠；同一段落/同一类事实（如年化利率、最高额度）只划入**一个**子页。
4. 每页 focus 必须写清 **include**（本页独有要点）与 **exclude**（已在其他页写、本页禁止展开），格式示例：
   `include: 利率与计息规则；exclude: 申请流程、准入条件、还款方式`
5. **`_index` 总览页**：focus 固定为「include: 产品定位与子页导航；exclude: 费率/额度/流程/材料等一切细则」；子页负责细节。
6. 子页维度可参考（按需 3~8 页，勿贪多）：产品概述、准入与申请、额度与期限、利率与费用、还款方式、担保与用途、其他须知。

## 输出
只输出 JSON，不要 Markdown 代码块：
{{
  "pages": [
    {{"folder": "{folder}", "slug": "_index", "title": "{product}", "focus": "include: 产品定位与子页导航；exclude: 费率/额度/流程/材料等细则"}},
    {{"folder": "{folder}", "slug": "主题名", "title": "主题名", "focus": "include: …；exclude: …"}}
  ]
}}

## 参考
source_id: {source_id}
source_title: {source_title}
split_mode: {split_mode}

source_text:
{source_text}

evidence_summary:
{evidence_text}
"""


def build_source_wiki_page_prompt(
    *,
    source_id: str,
    source_title: str,
    source_text: str,
    folder: str,
    slug: str,
    title: str,
    focus: str,
    evidence: dict[str, Any],
    required_wikilinks: list[str] | None = None,
    sibling_pages: list[dict[str, str]] | None = None,
    product_name: str = "",
    sibling_scope_hint: str = "",
) -> str:
    """Ask LLM to write one wiki page markdown for a planned outline entry."""
    evidence_text = json.dumps(evidence, ensure_ascii=False, indent=2)
    links = required_wikilinks or []
    links_block = "\n".join(f"- {link}" for link in links) if links else "- （无）"
    siblings = sibling_pages or []
    sibling_block = (
        "\n".join(f"- [[{folder}/{item['slug']}|{item['title']}]]" for item in siblings if item.get("slug") != slug)
        if siblings
        else "- （无）"
    )
    scope_block = sibling_scope_hint.strip() or "- （按 focus 的 exclude 自行避让其他页）"
    product = product_name or title
    index_rules = ""
    if slug == "_index":
        index_rules = """
## _index 专用
- 摘要 2~4 句 + 子页 wikilink 列表即可；**禁止**写费率、额度、流程步骤、材料清单等细则（一律留给子页）。
- 「要点」仅 2~4 条导航级信息，不得与子页要点重复。
"""

    return f"""## 角色
你是 AKOS Wiki 单页撰写助手。只写**当前这一页**的 Markdown 正文。

## 目标
只写当前页 Markdown 正文，**仅**覆盖 focus 中 include 的范围；遵守 exclude，不与 sibling 页重复。
{index_rules}

## 当前页
- folder: {folder}
- slug: {slug}
- title: {title}
- focus: {focus or title}
- product_name: {product}

## 页模板（必须包含）
## 摘要
## 要点          （至少 4~12 条具体事实：数字/条件/材料/费率/时限；可含小标题与表格）
## 常见问题      （3~8 条，带主体名）
## 相关原文
## Chunks
## 相关主题

## 规则
1. **优先**使用 evidence 中的 chunks/claims；source_text 仅为补充，**禁止**把其他章节/其他子页负责的内容抄进本页。
2. 必须包含 required wikilink：{links[0] if links else "source 链接"}。
3. **要点为主**：只写本页 focus 的 include；exclude 与下列 sibling 范围一律不写。
4. FAQ 3~8 条且须与本页主题相关；禁止全量倾倒 claims。
5. 相关主题优先链到 sibling 子页：
{sibling_block}

## 其他页分工（勿重复）
{scope_block}

## 输出
只输出 JSON：{{"markdown": "完整 Markdown 正文"}}

## 参考
source_id: {source_id}
source_title: {source_title}

required_wikilinks:
{links_block}

source_text:
{source_text}

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
    split_mode: str = "single",
    category: str = "",
    product_name: str = "",
) -> str:
    """One-shot prompt for short single-page sources (kept for compatibility)."""
    evidence_text = json.dumps(evidence, ensure_ascii=False, indent=2)
    old_block = json.dumps(old_pages or [], ensure_ascii=False, indent=2)
    catalog_block = json.dumps(wiki_catalog or [], ensure_ascii=False, indent=2)
    links = required_wikilinks or []
    links_block = "\n".join(f"- {link}" for link in links) if links else "- （无）"
    category_name = category or folder.split("/", 1)[0]
    product = product_name or default_slug

    return f"""## 角色
你是 AKOS Wiki 结构化编译助手。请为较短源文档生成 Wiki 页。

## 目标
默认一页：folder=`{folder}`，slug=`{default_slug}`，title=`{product}`。类目 `{category_name}`。

## 页模板
## 摘要 / ## 要点（4到12 条具体事实） / ## 常见问题（3到8） / ## 相关原文 / ## Chunks / ## 相关主题

## 规则
1. 只使用源文档与 evidence，不得编造。
2. 必须保留 required wikilinks。
3. 要点为主，禁止只复述一句 summary；FAQ 禁止全量倾倒 claims。

## 输出
只输出 JSON：
{{"pages":[{{"folder":"{folder}","slug":"{default_slug}","title":"{product}","markdown":"..."}}]}}

## 参考
source_id: {source_id}
source_title: {source_title}
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
