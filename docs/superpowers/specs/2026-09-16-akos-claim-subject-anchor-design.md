# AKOS Claim Subject 文档锚点（全文单产品）

**日期**: 2026-09-16  
**状态**: 已确认  
**依赖**:
- Hybrid LLM 抽取：`docs/superpowers/specs/2026-09-09-akos-hybrid-llm-extraction-design.md`
- Open predicate：`docs/superpowers/specs/2026-09-10-akos-open-predicate-extraction-design.md`

---

## 1. 动机

单产品说明书（如《青银理财成就系列（低波共享）》）抽取时，LLM 常把属性词当作 `subject`（如「还款方式」「收入要求」），导致多产品入库后同名属性 Claim 混桶，检索串产品。

需要：**一文档一产品**场景下，为全文解析产品锚点，并约束 Claim 三元组形态，使 `subject` 为产品实体名。

---

## 2. 已确认决策

| # | 决策 | 选择 |
|---|------|------|
| 1 | 锚点粒度 | **全文一个锚点**（一文档一产品） |
| 2 | 三元组形态 | **推荐写法**：`subject=产品名`，`predicate=属性/关系`，`object=值` |
| 3 | 非选用写法 | 不把「产品名的还款方式」整段写入 subject |
| 4 | 实现组合 | Prompt 规则（A）+ 文档锚点注入每 chunk（B） |
| 5 | 多产品合集文档 | **本阶段非目标**（如 `贷款产品合集.md`）；后续可做章节锚点 |
| 6 | 已有 Claim | 不自动回填；需重跑 LLM enrich / 重新上传 |

**规范示例：**

```text
subject   = 青银理财成就系列（低波共享）
predicate = 还款方式   # 或「包含」，以贴切为准
object    = 等额本息、等额本金、先息后本等多种还款方式
```

自然语言可读成「该产品的还款方式包含…」，但入库必须拆成上表三元组。与电商惯例一致：`(七天无理由, 适用类目, 非定制商品)`。

---

## 3. 数据流

```text
enrich_source / LLM 抽取路径
  → 读取 source 全文 + title
  → resolve_document_anchor(text, title) -> str | None
  → chunk_text(...)
  → 对每个 chunk:
       DomainLlmExtractor.extract(chunk, document_anchor=anchor)
  → apply_extracted_claims（不变）
```

### 3.1 锚点解析（启发式，不另开 LLM）

按优先级：

1. 正文表格式字段：匹配「产品简称」后紧随的非空行 / 同行值  
2. 正文「产品名称」字段（优先简称；全称过长时优先用简称）  
3. `source.title` 或文件名 stem（去掉扩展名）  
4. 皆空 → `document_anchor=None`，仅靠全局 Prompt 规则约束，不阻断抽取

### 3.2 Prompt 约束（全局）

在 `compiler/domain_llm_extractor.py` 的 `_PROMPT`「规则」中增加：

- `subject` 必须是原文中的**具体产品名、政策/规则名或主题实体**，禁止单独使用属性词（如「利率」「额度」「还款方式」「收入要求」）作 subject。  
- 属性写入 `predicate`，取值写入 `object`。  
- 若提供 `document_anchor`：本段 Claim 的 `subject` **应使用该锚点**（或原文中与之同指的产品全称/简称），不要改用泛化属性词。

配置 JSON 增加可选字段 `document_anchor`（有则注入）。

### 3.3 Domain few-shot

`loan_finance`（及需要的 generic）补充 `few_shot_hints` 正反例，例如：

- 正例：`subject=青银理财成就系列（低波共享），predicate=还款方式，object=等额本息…`  
- 反例：`subject=还款方式` ❌

---

## 4. 模块

| 模块 | 职责 |
|------|------|
| `compiler/document_anchor.py`（新建） | `resolve_document_anchor(text: str, title: str \| None = None) -> str \| None` |
| `compiler/domain_llm_extractor.py` | Prompt 规则；`extract(..., document_anchor=None)`；`_build_prompt` 注入锚点 |
| `compiler/enrichment.py` | 调锚点解析并传入每 chunk |
| 其它 LLM 抽取入口（若有同步路径） | 同样传入锚点，避免分叉 |
| `domains/loan_finance/domain.py` | few_shot_hints |
| 测试 | 锚点解析 fixture；extractor prompt 含锚点与规则 |

---

## 5. 非目标

- 一文档多产品的章节级锚点  
- 属性黑名单硬拒收 / quarantine（可作为后续增强）  
- 批量改写历史 Claim（依赖重跑 enrich）  
- 改变检索公式或 Claim schema 字段  

---

## 6. 测试与验收

- 单元：给定含「产品简称」+ 青银系列名的文本 → 锚点解析命中简称  
- 单元：`_build_prompt` 在传入 anchor 时包含该字符串与 subject 规则  
- 手工/集成：对单产品说明书重跑 enrich 后，抽样 Claim 的 subject 含产品名；「还款方式」出现在 predicate 而非单独作 subject  

---

## 7. 与检索的关系

索引文本仍为 `"{subject} {predicate} {object}"`。  
规范写法下，问「成就系列 还款方式」可同时命中产品主体与属性谓词，并避免跨产品「还款方式」主体碰撞。
