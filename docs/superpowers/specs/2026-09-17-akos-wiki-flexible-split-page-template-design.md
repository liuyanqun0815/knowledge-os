# Wiki 灵活拆分与页模板（要点 + 精选 FAQ）

**Date:** 2026-09-17  
**Status:** Approved (方案 B, 消费者 C：人读 + Ask)  
**Scope:** `wiki/prompts.py`, `wiki/source_plan.py`, fallback 拆分，相关测试

## Goal

1. 长文档是否拆页由阈值/启发式决定；**如何拆页由 LLM 按业务主题灵活决定**，不写死「一、二、」或「## 1. 产品」样例结构。
2. Wiki 页以**结构化要点**为主，每页仅 **3~8 条高频 FAQ**；禁止把全量 Claim 倾倒成问答。

## Non-goals

- 不改 Claim 萃取与 Ask 权威链路。
- 不引入两阶段「先聚类再写页」的多轮 LLM（方案 C 留作后续）。
- 不强制重新编译全部历史 KB（调用方按需 recompile）。

## Decisions

| ID | Decision |
|----|----------|
| D1 | `single` / `bundle`：系统只判定要不要拆 + 类目 folder；子页边界由 LLM 决定 |
| D2 | 统一页模板：摘要 → 要点 → 常见问题(3~8) → 相关原文 → Chunks → 相关主题 |
| D3 | LLM 失败时的 fallback：按 chunk `topics` / `section_path` / `title` 聚类，最多 8 子页 + `_index`；不再硬切中文章节号 |
| D4 | FAQ 必须带主体名；从本页相关 claim 精选，优先额度/利率/条件/材料/赎回等客服高频谓词 |
| D5 | bundle 模式下若 LLM 只产出 1 页 → 视为失败，走 D3 fallback |

## Page template

```markdown
# {title}

## 摘要
> …

## 要点
- …（可含表格）

## 常见问题
### {主体}：{问题}
- **答**：…
- **来源**：[[source-…|…]]

## 相关原文
## Chunks
## 相关主题
```

## Prompt rules (summary)

- 取消「问答应覆盖该页全部 claims」。
- 要求：要点为主；常见问题 3~8 条；禁止裸 predicate。
- bundle：子页可按产品、场景、主题拆，不要求复刻源文档目录。

## Fallback FAQ selection

- 输入：本页相关 claims（subject/title/body 匹配）。
- 打分：高频谓词关键词加权 + 置信度。
- 输出：去重后最多 8 条；不足则有多少写多少。

## Test plan

- Prompt/编译：fallback 页含 `## 要点` 与 `## 常见问题`，FAQ ≤ 8。
- bundle fallback：多 chunk 不同 topic → 多子页，且非强制「一、」切分。
- 现有 catalog/product 测试改为 topic 聚类语义或保留宽松断言。
