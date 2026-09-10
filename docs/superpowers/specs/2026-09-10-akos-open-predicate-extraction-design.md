# AKOS 开放谓词 LLM 抽取设计规格（方案 C）

**日期**: 2026-09-10  
**状态**: 待用户审阅  
**依赖**:
- `docs/superpowers/specs/2026-09-09-akos-hybrid-llm-extraction-design.md`（Hybrid 规则+异步 LLM 补抽）
- 现有链路：`DomainLlmExtractor` → `KnowledgeCompiler.apply_extracted_claims` → Ontology / quarantine
**原则**: 尽量少人工；按文件内容自由抽 SPO；用 quote/置信度等硬门替代谓词白名单硬拒绝；新谓词懒注册进 ontology，保持图一致。

---

## 1. 动机

当前 LLM prompt 注入固定 `allowed_predicates` / `entity_types`（按 domain seed）。模型被引导只抽白名单关系；白名单外进入 `invalid_predicate` / `unknown_predicate` quarantine。

结果：文档里大量有效知识（尤其跨主题政策）抽不出或进待审，问答覆盖不足。用户选择 **方案 C：几乎全开放，尽量少人工**。

---

## 2. 已确认决策

| # | 决策 | 选择 |
|---|------|------|
| 1 | 开放程度 | **开放谓词**：prompt 不强制白名单；suggested 仅作参考 |
| 2 | 新谓词落库 | **过质量门后直接 active**（或既有 staging 冲突规则） |
| 3 | Ontology | **懒注册**：首次出现的 `(subject_type, predicate, object_type)` 写入进程内 ontology，再校验通过 |
| 4 | 实体类型 | **建议列表**；解析不到时仍默认 `Concept`（与现网一致） |
| 5 | 质量门 | **保留**：`quote ∈ 原文`、`confidence ≥ min`、字段非空；不合格仍 quarantine |
| 6 | 开关 | **`AKOS_EXTRACT_OPEN_PREDICATES`**（**默认 `true`**；关闭则回退现网白名单硬拒绝） |
| 7 | 规则抽取 | **不变**：`RuleExtractor` 仍只产生白名单内规则命中 |

---

## 3. 与现网行为差异

| 路径 | 关闭开放（现网） | 开启开放（本规格） |
|------|------------------|-------------------|
| Prompt | `allowed_predicates` 强约束语气 | `suggested_predicates` + 明确允许自创谓词 |
| `validate_claim` 失败 | quarantine `invalid_predicate` | **懒注册 predicate 后写入**（不因名单拒绝） |
| `Concept`↔`Concept` | 已放行（现 ontology） | 不变 |
| low_confidence / span_missing | quarantine | **不变** |
| 高风险核验 verify_sample | 按 domain `high_risk_predicates` | **不变**（仅名单内高风险仍严核） |

---

## 4. 架构与改动点

### 4.1 配置

```text
AKOS_EXTRACT_OPEN_PREDICATES=true
AKOS_EXTRACT_MIN_CONFIDENCE=0.5   # 已有
```

`infra/settings.py` / `.env.example` 增加 `extract_open_predicates: bool`。

### 4.2 `LlmExtractionSpec`

```python
@dataclass
class LlmExtractionSpec:
    allowed_predicates: list[str]      # 开放模式下语义变为 suggested
    entity_types: list[str]            # 同上 suggested
    prompt_locale: str = "zh"
    few_shot_hints: list[str] | None = None
    open_predicates: bool = False      # 由 Settings 注入或 domain 覆盖
```

Domain 的 `llm_extraction_spec()` 可继续返回 seed 列表作 suggested；**是否开放由全局 Settings 控制**（避免每个 domain 分叉）。

### 4.3 Prompt（`DomainLlmExtractor`）

开放模式配置 JSON 示例：

```json
{
  "mode": "open",
  "suggested_predicates": ["适用", "排除", "..."],
  "suggested_entity_types": ["Policy", "Concept", "..."],
  "prompt_locale": "zh",
  "few_shot_hints": [],
  "rules": [
    "可使用最贴切的中文谓词，不必限于 suggested_predicates",
    "quote 必须是原文连续非空子串",
    "只输出 json_schema 对应的 JSON 数组"
  ]
}
```

关闭模式保持现有 `allowed_predicates` 字段与强约束文案，兼容旧测试。

### 4.4 Compiler 懒注册（`apply_extracted_claims`）

在现有 `validate_claim` 失败分支：

```text
if not ontology.validate_claim(st, pred, ot):
    if settings.extract_open_predicates:
        ontology.register_predicate(st, pred, ot)
        # 可选：register_entity(subject/object) 若尚未注册
    else:
        quarantine(invalid_predicate); continue
# 继续 append_claim / graph / evidence / index
```

**同步 `ingest` 规则路径**：不启用开放懒注册（规则结果本就在名单内）；仅 LLM `apply_extracted_claims` / Enrichment 路径受开关影响。

### 4.5 轻量归一（可选一期最小）

本期 **不做** LLM 二次归一。仅文档约定：后续可用 alias 表合并「适用/适用于」。不阻塞开放入库。

---

## 5. 数据流

```text
EnrichmentRunner / DomainLlmExtractor
  └─ open prompt → JSON claims
       │
       ▼
KnowledgeCompiler.apply_extracted_claims
  ├─ confidence < min     → quarantine low_confidence
  ├─ quote not in text    → quarantine span_missing
  ├─ validate fail
  │     ├─ open=true      → register_predicate → 写入 active/staging
  │     └─ open=false     → quarantine invalid_predicate
  └─ 写入 claim + graph + evidence + index_claim
```

检索侧：`warm_index` 已从 PG 重建 active；开放后更多 claim 可被 CLAIM 子串命中（中文分词增强为独立议题）。

---

## 6. 验收标准

1. `AKOS_EXTRACT_OPEN_PREDICATES=true` 时：LLM mock 返回白名单外谓词（如 `"发货时效"`），且 quote 合法、confidence 达标 → **产生 active Claim**，不进 `invalid_predicate`
2. 同开关下：confidence 过低或 quote 不在原文 → 仍 quarantine
3. `AKOS_EXTRACT_OPEN_PREDICATES=false` 时：行为与现网一致（名单外 quarantine）
4. 开放写入后，同进程 `HybridRetrieval` 能检索到该 Claim；重启后 `warm_index` 仍可命中
5. 相关单测：`test_domain_llm_extractor`（prompt 含 open/suggested）、`test_compiler` / enrich 路径懒注册

### 6.1 测试要点

- Prompt：`mode=open` 时出现「不必限于」类文案，且字段名为 `suggested_predicates`
- Compiler：open 下 `register_predicate` 被调用且 `claims_created += 1`
- 回归：关闭开关时 `invalid_predicate` 计数不变

---

## 7. 非目标

- 人工审核作为开放谓词的主路径（方案 B）
- 按文档自动生成并落盘整套 domain seed 文件
- 谓词同义自动合并（alias LLM）
- 中文分词 / 检索算法大改
- 同步路径把 LLM 拉进 `compile_node`

---

## 8. 风险与缓解

| 风险 | 缓解 |
|------|------|
| 谓词碎片化 | 后续 alias；本期接受 |
| 噪声 Claim | quote + confidence 硬门；可调高 `AKOS_EXTRACT_MIN_CONFIDENCE` |
| Ontology 仅进程内懒注册、不落盘 | 与现 InMemoryOntology 一致；重启靠 seed + 再次懒注册；Claim 已在 PG |
| 图上出现大量非常规边类型 | 可接受；问答以 Claim 为主 |

---

## 9. 成功一句话

> 打开开放谓词开关后：模型按文档内容自由抽关系；合法 quote 与置信度通过即入库并可问；不再因「不在固定抽取配置里」而丢知识。
