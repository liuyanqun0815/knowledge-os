# AKOS Hybrid LLM 抽取设计规格 — 规则保底 + 异步补抽

**日期**: 2026-09-09  
**状态**: 已确认（brainstorming）  
**依赖**:
- 一期/二期规格：`docs/superpowers/specs/2026-09-08-akos-ecommerce-cs-design.md`、`2026-09-08-akos-phase2-design.md`
- 现有链路：`admin_api` 上传 → `orchestrator.ingest` → `ingest_graph` → `KnowledgeCompiler`
**原则**: 保持 Source→Claim→Evidence 的 Knowledge OS 模型；不把系统做成纯 Chunk-RAG；名单外谓词不直接污染主图

---

## 1. 动机

当前电商等领域默认 `RuleExtractor`（少量正则），`LlmExtractor` 仅企业文化且写死 prompt。非规则命中文本 Claim 很少或为 0，无法满足「任意文档萃成可问答知识」。

本规格补齐：

1. **LLM 通用高质量抽取**（按领域注入白名单与 prompt）  
2. **任意文档更丰富的 Claim 覆盖**（切片补抽 + 去重合并）  
3. 同时保留一期可测的规则基线与上传体验

---

## 2. 已确认决策

| # | 决策 | 选择 |
|---|------|------|
| 1 | 抽取策略 | **Hybrid**：规则 + LLM 补抽；`AKOS_EXTRACT_RULES` / `AKOS_EXTRACT_LLM` 可关 |
| 2 | 未知谓词 | **白名单优先**；名单外进 quarantine/staging（`unknown_predicate`），不直接 active |
| 3 | 上传时序 | **两段式**：同步仅规则 → 立刻可问答；LLM **后台补抽**再合并 |
| 4 | 长文 | **切片** + 硬上限：单片 ≤ N 字、单文档 ≤ M 片；超出 → `succeeded_partial` |
| 5 | 实现形态 | **进程内** FastAPI `BackgroundTasks` + 启动扫描 `enriching` 重试（不做 Redis Worker） |

---

## 3. 架构与数据流

### 3.1 组件

| 组件 | 职责 |
|------|------|
| `HybridExtractor` | 组合 Rule + LLM；按开关启用一侧或两侧 |
| `DomainLlmExtractor` | 按 `domain_type` 注入允许谓词、实体类型、中文示例到 prompt |
| `TextChunker` | 按标题/段落切片；执行 `AKOS_CHUNK_MAX_CHARS` / `AKOS_CHUNK_MAX_PER_DOC` |
| `EnrichmentRunner` | 后台对已有 `source_id` 做 LLM 补抽、去重写入、更新状态 |
| `KnowledgeCompiler` | 保持 Ontology 校验、Claim/图/证据/索引；非法谓词 quarantine |

### 3.2 两段式数据流

```text
POST /admin/knowledge-bases/{id}/sources/upload
  │
  ├─① 同步（秒级）
  │    store → compile(仅 Rule，或 llm_enabled=False 的 Hybrid)
  │    verify_sample（现有）
  │    [可选] evolve（replaces_source_id）
  │    source 状态 → enriching（若 LLM 开启且已配置 Key）或 succeeded
  │    返回 CompileReport（规则 Claim 已可检索）
  │
  └─② BackgroundTasks: EnrichmentRunner
       chunk(source_text)
       → 逐片 DomainLlmExtractor
       → 去重合并写入
       → 白名单外 → quarantine(unknown_predicate)
       → 更新 enrichment 进度与终态
```

### 3.3 与 ingest_graph 边界

| 阶段 | 调用 | Extractor |
|------|------|-----------|
| 同步上传 | 现有 `store → compile → verify_sample → [evolve]` | **仅规则** |
| 后台补抽 | **不重跑整图**；`EnrichmentRunner` 走 Compiler 写入路径 | **仅 LLM** |
| `replaces_source_id` | 同步 staging + evolve 不变；补抽对 new source 遵循同一 staging 规则 | 与演化一致 |

**禁止**把 LLM 放进同步 `compile_node`，避免上传超时。

---

## 4. 合并去重、状态机、失败

### 4.1 合并规则

| 规则 | 行为 |
|------|------|
| 同 `family_id` 且 object 相同 | 跳过（规则已覆盖） |
| 同 family、object 不同、均 active | 新 Claim 进 **staging**；不自动 supersede（应走 evolve/人工） |
| quote 无法在原文定位 | quarantine(`span_missing`) 或丢弃，不入主图 |
| 谓词不在白名单 | quarantine(`unknown_predicate`)，payload 含谓词与 quote |
| confidence < 阈值（默认 0.5） | quarantine(`low_confidence`) |

`family_id` 与现 `KnowledgeCompiler._family_id` 一致。

### 4.2 Source 状态机

```text
pending → running
       → enriching            # LLM 补抽中（规则 Claim 已可用）
       → succeeded            # 规则+LLM 完成，或未开 LLM 且规则完成
       → succeeded_partial    # 规则成功但 LLM 跳过/部分片失败/超切片上限
       → failed               # 规则阶段失败，或策略要求标失败
```

### 4.3 失败与降级

| 情况 | 处理 |
|------|------|
| 无 `AKOS_LLM_API_KEY` | 跳过②；`enrichment=skipped`，可用 `succeeded` 或 `succeeded_partial` |
| 单片超时/坏 JSON | 重试 1 次；失败记 error，继续后续片 |
| ≥50% 片失败 | `succeeded_partial`，保留已成功 Claim |
| 进程重启 | lifespan 扫描 `enriching`，重新调度 EnrichmentRunner |
| 规则 0 条且 LLM 关闭 | `succeeded` + claims=0；管理台提示配置 Key 或规则 |

### 4.4 API 扩展（可选字段，旧客户端忽略）

`SourceResponse` 增加：

- `enrichment_status`: `skipped` | `running` | `done` | `failed`
- `claims_from_rules` / `claims_from_llm` / `quarantined_count`
- `chunks_total` / `chunks_done`

管理台文档页：enriching 时继续轮询；文案区分「规则已可用 / LLM 补抽中」。

---

## 5. 模块落点

```text
compiler/
├── hybrid_extractor.py
├── domain_llm_extractor.py
├── chunker.py
├── enrichment.py
├── rule_extractor.py          # 保留
└── llm_extractor.py           # 委托或瘦身

domains/*/domain.py
  + llm_extraction_spec()      # predicates / entity_types / prompt hints
  # generic：较宽谓词（规定/适用于/禁止/要求）仍对未知走 quarantine

admin_api/routes_sources.py
  上传成功后 BackgroundTasks.add_task(enrich, kb_id, source_id)

app/main.py
  lifespan：resume enriching sources

infra/settings.py, .env.example
```

### 5.1 配置默认值

```text
AKOS_EXTRACT_RULES=true
AKOS_EXTRACT_LLM=true
AKOS_CHUNK_MAX_CHARS=3000
AKOS_CHUNK_MAX_PER_DOC=40
AKOS_EXTRACT_MIN_CONFIDENCE=0.5
```

无 Key 时视为 LLM 不可用，自动跳过补抽（即使 `AKOS_EXTRACT_LLM=true`）。

### 5.2 Domain LLM 规格（示意）

```python
@dataclass
class LlmExtractionSpec:
    allowed_predicates: list[str]
    entity_types: list[str]
    prompt_locale: str = "zh"
    few_shot_hints: list[str] | None = None
```

电商：沿用现有谓词白名单（适用类目、排除、运费承担方等）。  
企业文化：倡导、禁止、适用于。  
generic：规定、适用于、禁止、要求（可扩展但仍有限）。

---

## 6. 验收标准

1. 电商样本文档：规则 Claim ≥ 现基线；配置 Key 后另有 ≥1 条**仅 LLM**补出的白名单内 Claim  
2. 文档含白名单外关系句 → 出现 `unknown_predicate` quarantine；主检索不命中该条  
3. 上传同步阶段不调用 LLM（可用单测/mock 断言）；P95 不因 LLM 显著变慢  
4. `AKOS_EXTRACT_LLM=false` 时与当前规则抽取行为一致；一期相关 e2e 仍 PASS  
5. 超过 `AKOS_CHUNK_MAX_PER_DOC` → `succeeded_partial` + 可观测的「未抽完」标记  

### 6.1 测试

- 单元：`HybridExtractor`、`TextChunker` 边界、未知谓词路径  
- 集成：mock LLM 固定 JSON，断言补抽后 Claim/quarantine 计数与状态迁移  
- 回归：无 Key / 关 LLM 时既有 ingest/e2e 通过  

---

## 7. 非目标

- Redis/独立 Enrich Worker（可后续从 EnrichmentRunner 抽出）  
- PDF OCR / 扫描件  
- 未知谓词自动写入正式 Ontology  
- 图片、表格多模态抽取  
- 同步 Full Hybrid（规则+LLM 同请求）  

---

## 8. 与二期规格关系

二期目标含「LLM 抽取」且 2.1 明确「完整 LLM 抽取质量调优」不在 2.1 范围。本规格作为 **独立抽取增强规格**，可在 2.1+ 并行实现；实现后建议在 phase2 design 中引用本文件。

---

## 9. 成功一句话

> 上传任意支持的文本文档：规则秒级入库可问；LLM 后台切片补抽丰富 Claim；名单外关系进待审；关闭 LLM 时行为与现网一致。
