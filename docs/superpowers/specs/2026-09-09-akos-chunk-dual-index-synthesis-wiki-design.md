# AKOS Chunk 双索引 + LLM 合成回答 + Wiki 升级 — 设计规格

**日期**: 2026-09-09  
**状态**: 待确认（brainstorming → 设计评审）  
**依赖**:
- `2026-09-08-akos-phase2-design.md`（Knowledge OS 核心模型）
- `2026-09-09-akos-hybrid-llm-extraction-design.md`（Hybrid 抽取）
- 现有链路：`ingest_graph` / `ask_graph` / `HybridRetrieval` / `wiki/export.py`

**原则**:
1. **Claim 管结构化事实，Chunk 管叙述性内容** — 双索引互补，不互相替代
2. **原文 100% 可检索** — Chunk 分区覆盖全文，不允许「未索引盲区」
3. **LLM 用于组织与表达，不用于捏造事实** — synthesis 必须绑定 evidence / chunk 引用
4. **渐进增强** — 各能力可独立开关；LLM 不可用时降级到现有模板回答

---

## 1. 动机与目标

### 1.1 现状问题

| 问题 | 根因 |
|------|------|
| 大量正文无法问答 | 只有 Claim 进检索索引；叙述性段落未结构化则不可见 |
| 回答生硬 | `answer_node` 模板拼接 Claim，无 LLM 综合 |
| Wiki 价值有限 | `export_wiki()` 机械列出 Claim，无摘要与上下文 |
| 复杂问答弱 | 多跳依赖 Graph + 少量 Claim，缺少段落级上下文 |

### 1.2 目标

| # | 能力 | 成功标准 |
|---|------|----------|
| G1 | Chunk 级入库 | 任意上传文档每个字符属于且仅属于一个 active chunk；chunk 可独立检索 |
| G2 | Claim + Chunk 双索引 | 简单事实问答走 Claim；解释/流程/背景类走 Chunk；HYBRID 融合 |
| G3 | LLM synthesis | Ask 输出自然语言 + 引用；无 evidence 时拒绝或降级 |
| G4 | Wiki LLM 升级 | export 生成 entity/source 摘要段；Claim 列表保留 |

---

## 2. 已确认决策（待评审）

| # | 决策 | 选择 | 理由 |
|---|------|------|------|
| D1 | Chunk 切分主策略 | **结构切分保底 + LLM 标注/合并建议** | 100% 覆盖靠确定性算法；LLM 提升语义边界 |
| D2 | Chunk 向量 | **Phase 1**: char-hash + BM25（与现 Hybrid 一致）；**Phase 2**: 可选 embedding API | 降低首期依赖 |
| D3 | Chunk 入库时机 | **同步**：结构切分 + 索引；**后台**：LLM 标题/摘要/主题 enrichment | 避免上传超时 |
| D4 | 双索引融合 | **Reciprocal Rank Fusion (RRF)** 或加权分数合并 | 简单稳健，不引入 reranker 模型 |
| D5 | synthesis 触发 | `AKOS_ASK_SYNTHESIS=true` 且 LLM 已配置；否则走现有 `answer_node` | 可降级 |
| D6 | synthesis 输入 | verified claims + evidence quotes + top chunk hits | 严格 grounding |
| D7 | Wiki LLM | export 时可选；按 content_hash 缓存摘要 | 避免重复调用 |
| D8 | Claim 抽取 | 维持规则∪LLM 并集（已实现） | 与 Chunk 互补 |

---

## 3. 数据模型

### 3.1 新增 `SourceChunk`

```python
@dataclass
class SourceChunk:
    id: str                          # uuid
    source_id: str
    chunk_index: int                 # 0..n-1，文档内顺序
    title: str | None                # LLM/标题行提取
    summary: str | None              # LLM 生成（后台 enrichment）
    text: str                        # chunk 正文
    start: int                       # 在 source_text 中的 byte/char offset
    end: int
    section_path: list[str]          # 如 ["物流", "发货时效"]
    topics: list[str]                # LLM 关键词
    token_count: int
    status: str                      # active | stale
    content_hash: str                # sha256(text)，用于 Wiki/摘要缓存
    created_at: datetime
```

**覆盖不变量**（ ingest 校验）:

```text
∀ source S with text T:
  chunks = list_chunks(S.id, status=active)
  sort by chunk_index
  assert chunks[0].start == 0
  assert chunks[-1].end == len(T)
  assert ∀i: chunks[i].end == chunks[i+1].start
  assert concat(chunks[i].text) == T   # 或通过 span 重建等价
```

### 3.2 扩展 `Hit`

```python
@dataclass
class Hit:
    hit_type: Literal["claim", "chunk"]   # 新增
    claim_id: str | None
    chunk_id: str | None                  # 新增
    source_id: str | None                 # chunk hit 直接携带
    score: float
    snippet: str | None
    entity_id: str | None = None
```

### 3.3 扩展 `Answer`

```python
@dataclass
class Answer:
    text: str
    claim_ids: list[str]
    chunk_ids: list[str]                  # 新增
    evidence: list[dict[str, Any]]        # 含 claim quote
    chunk_citations: list[dict[str, Any]] # 新增: source_id, chunk_id, quote
    synthesis_used: bool                    # 新增
    confidence: float
    ...
```

### 3.4 扩展 `AskState`

```python
class AskState(TypedDict):
    ...
    chunk_hits: list[Hit]
    chunk_ids: list[str]
    synthesis_context: dict | None          # 传给 synthesize_node 的打包上下文
    synthesis_skipped_reason: str | None
```

### 3.5 PostgreSQL 迁移 `005_source_chunks.sql`

```sql
CREATE TABLE source_chunks (
    id UUID PRIMARY KEY,
    knowledge_base_id TEXT NOT NULL REFERENCES knowledge_bases(id),
    source_id TEXT NOT NULL,
    chunk_index INT NOT NULL,
    title TEXT,
    summary TEXT,
    text TEXT NOT NULL,
    start_offset INT NOT NULL,
    end_offset INT NOT NULL,
    section_path JSONB DEFAULT '[]',
    topics JSONB DEFAULT '[]',
    token_count INT DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'active',
    content_hash TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (knowledge_base_id, source_id, chunk_index)
);
CREATE INDEX idx_source_chunks_kb_source ON source_chunks(knowledge_base_id, source_id);
CREATE INDEX idx_source_chunks_hash ON source_chunks(content_hash);
```

`KnowledgePort` 扩展:

```python
def save_chunks(self, source_id: str, chunks: list[SourceChunk]) -> None: ...
def list_chunks(self, source_id: str, *, status: str = "active") -> list[SourceChunk]: ...
def get_chunk(self, chunk_id: str) -> SourceChunk | None: ...
def delete_chunks_for_source(self, source_id: str) -> None: ...
```

---

## 4. Chunk 入库流水线

### 4.1 模块划分

| 模块 | 路径（建议） | 职责 |
|------|-------------|------|
| `StructuralChunker` | `compiler/chunker.py`（扩展） | 标题/段落切分 + 硬切；输出带 offset |
| `ChunkLlmEnricher` | `compiler/chunk_enrichment.py`（新） | LLM 生成 title/summary/topics；失败则跳过 |
| `ChunkIndexer` | `retrieval/chunk_index.py`（新） | BM25 + char-hash 向量索引 |
| `ChunkService` | `compiler/chunk_service.py`（新） | 编排切分、持久化、索引 |

### 4.2 切分算法（同步，确定性）

在现有 `chunk_text()` 基础上扩展为 **带 offset 的 `chunk_document()`**:

```text
1. _split_sections(text) → sections（已有）
2. 对每个 section：
     若 section 是标题行 → 更新 section_path 栈
     若 len(section) > max_chars → _hard_split 并累计 offset
3. 生成 SourceChunk 列表，填充 start/end/section_path
4. 校验覆盖不变量；失败 → compile error
```

**不依赖 LLM 完成切分**，保证无 Key 时也能 100% 索引。

### 4.3 LLM Chunk Enrichment（后台，可选）

触发：`AKOS_CHUNK_LLM_ENRICH=true` 且 LLM 已配置，在 `enrich_source` 之后或并行任务。

Prompt 输出 JSON（每 chunk 一条）:

```json
{
  "chunk_index": 0,
  "title": "发货时效说明",
  "summary": "节假日顺延，48小时内发货。",
  "topics": ["发货", "时效", "节假日"]
}
```

校验：
- `chunk_index` 必须存在
- 不修改 `text` / offset（LLM 只标注，不改边界）
- 失败重试 1 次；仍失败则保留无 summary 的 chunk（仍可检索）

### 4.4 Ingest 图扩展

```text
store → compile(Claim) → index_chunks(同步) → verify_sample → [evolve]
                              ↓
                    BackgroundTasks:
                      enrich_source (Claim LLM)
                      enrich_chunks (Chunk LLM 标注)
```

新增 `index_chunks_node`:

```python
def index_chunks_node(state, deps):
    source_id = state["source_id"]
    text = deps.knowledge.get_source_text(source_id)
    chunks = chunk_service.build_and_save(source_id, text, settings)
    deps.chunk_retrieval.index_chunks(chunks)
    return {"chunk_report": {"chunks_created": len(chunks), ...}}
```

**文档替换** (`replaces_source_id`):
- 旧 source chunks → `status=stale`
- 新 source 重新切分索引
- evolve 激活新 Claim 后，chunk 无需 staging（chunk 不参与 family 冲突）

### 4.5 配置项

| 变量 | 默认 | 说明 |
|------|------|------|
| `AKOS_CHUNK_INDEX` | `true` | 关闭则退回纯 Claim 模式 |
| `AKOS_CHUNK_MAX_CHARS` | `3000` | 与 enrichment 共用 |
| `AKOS_CHUNK_MAX_PER_DOC` | `40` | 超出 → `succeeded_partial` + 尾部 chunk 仍覆盖至文末 |
| `AKOS_CHUNK_LLM_ENRICH` | `true` | 后台 LLM 标注 |
| `AKOS_CHUNK_EMBEDDING` | `false` | Phase 2：真实 embedding |

---

## 5. Claim + Chunk 双索引检索

### 5.1 架构

```text
                    ┌─────────────────┐
                    │   User Query    │
                    └────────┬────────┘
                             │
              ┌──────────────┴──────────────┐
              ▼                             ▼
    ┌──────────────────┐          ┌──────────────────┐
    │ HybridRetrieval  │          │ ChunkRetrieval   │
    │ (Claim+Graph+    │          │ (BM25+Vector on  │
    │  BM25+Vector)    │          │  chunk text)     │
    └────────┬─────────┘          └────────┬─────────┘
              │                             │
              └──────────────┬──────────────┘
                             ▼
                    ┌─────────────────┐
                    │  Fusion Ranker  │
                    │  (RRF / weighted)│
                    └────────┬────────┘
                             ▼
                    claim_ids + chunk_ids
```

### 5.2 `ChunkRetrieval` 接口

```python
class ChunkRetrievalPort(Protocol):
    def index_chunks(self, chunks: list[SourceChunk]) -> None: ...
    def remove_source(self, source_id: str) -> None: ...
    def warm_index(self) -> None: ...
    def search(self, query: str, filters: dict) -> list[Hit]: ...
```

索引字段（拼接后索引）:

```text
index_text = f"{title} {summary} {' '.join(topics)} {text}"
```

### 5.3 融合策略

**RRF（推荐）**:

```python
def rrf_score(rank: int, k: int = 60) -> float:
    return 1.0 / (k + rank)

# 对 claim_hits 与 chunk_hits 分别排名后求和
```

**路由增强** (`retriever_agent.route_mode`):

| 问题特征 | Claim 权重 | Chunk 权重 |
|----------|-----------|-----------|
| 含「为什么/为何/怎么/如何/流程」 | 0.3 | 0.7 |
| 含「是什么/多少/谁/何时」+ 实体 | 0.7 | 0.3 |
| 含「关系/关联/之间」 | Graph + Claim 0.5 | 0.5 |
| 默认 HYBRID | 0.5 | 0.5 |

### 5.4 `retrieve_node` 改造

```python
def retrieve_node(state, deps):
    question = state.get("normalized_question") or state["question"]
    mode = state.get("retrieval_mode") or RetrievalMode.HYBRID

    claim_hits = retriever_agent.retrieve(deps.retrieval, question, mode, as_of)
    chunk_hits = []
    if settings.chunk_index:
        chunk_hits = deps.chunk_retrieval.search(question, {"top_k": settings.retrieval_top_k})

    fused_hits = fusion_rank(claim_hits, chunk_hits, question)
    return {"hits": fused_hits, "chunk_hits": chunk_hits, ...}
```

### 5.5 `verify_node` 适配

- Claim：沿用现有 `verification_agent.verify_claims`
- Chunk：**不做 ontology 校验**；仅校验 `chunk.text` 非空、source 存在
- 可选：chunk hit 与 claim hit 同 source 时提升 confidence

---

## 6. Ask 图：LLM Synthesis 节点

### 6.1 图结构变更

```text
recall → parse_time → normalize → route_mode → retrieve → verify → explain
                                                                    ↓
                                                              synthesize  ← 新增
                                                                    ↓
                                                                 answer → remember
```

条件边：

```text
explain → synthesize  if AKOS_ASK_SYNTHESIS && llm configured && (claim_ids or chunk_ids)
explain → answer      otherwise（synthesize 内部也可 fallback）
synthesize → answer
```

### 6.2 `synthesize_node` 职责

**输入打包** (`build_synthesis_context`):

```python
{
  "question": str,
  "claims": [
    {"id", "subject", "predicate", "object", "confidence"}
  ],
  "evidence": [
    {"source_id", "quote", "claim_id"}
  ],
  "chunks": [
    {"id", "source_id", "title", "summary", "text_excerpt"}  # excerpt ≤ 500 字
  ],
  "procedure": optional,
  "as_of": optional,
}
```

**Prompt 要点**:

```text
你是 AKOS 知识库问答助手。仅根据提供的 claims 与 chunks 回答，禁止编造。
要求：
1. 用中文自然语言回答用户问题
2. 每个事实句末标注引用 [source_id:简短quote]
3. 若 claims 冲突，说明冲突并列出双方
4. 若信息不足，明确说「依据不足」
输出 JSON: {"answer": "...", "citations": [{"source_id", "quote", "claim_id"|null, "chunk_id"|null}]}
```

**输出处理**:

1. 解析 JSON；失败 → fallback 模板 answer
2. 校验每个 citation 的 quote 是 context 中某条的子串
3. 不通过 → 降级模板 answer + `synthesis_skipped_reason="citation_invalid"`
4. 通过 → 写入 `state["synthesis_text"]`，`answer_node` 优先使用

### 6.3 `answer_node` 改造

```python
def answer_node(state, deps):
    if state.get("synthesis_text"):
        return Answer(text=synthesis_text, synthesis_used=True, chunk_citations=..., ...)
    # 现有模板逻辑（fallback）
```

**Guardrails（硬约束）**:

| 条件 | 行为 |
|------|------|
| 无 claim 且无 chunk | 拒绝回答（已有） |
| verification.confidence < 0.4 | 拒绝（已有） |
| synthesis citations 校验失败 | 降级模板 |
| LLM 超时/异常 | 降级模板 |
| `AKOS_ASK_SYNTHESIS=false` | 跳过 synthesize |

### 6.4 配置

| 变量 | 默认 | 说明 |
|------|------|------|
| `AKOS_ASK_SYNTHESIS` | `true` | 开启 LLM 合成 |
| `AKOS_ASK_SYNTHESIS_TEMPERATURE` | `0.2` | 低温度减少幻觉 |
| `AKOS_ASK_SYNTHESIS_MAX_CHUNKS` | `5` | 传入 LLM 的 chunk 数 |
| `AKOS_ASK_SYNTHESIS_MAX_TOKENS` | `1024` | 回答长度上限 |

### 6.5 LangSmith 追踪

- `@traceable(name="akos.synthesize_answer")` 包裹 synthesize_node
- metadata: `claim_count`, `chunk_count`, `fallback_reason`

---

## 7. Wiki 升级：LLM 摘要 export

### 7.1 目标页面结构

**Source 页**（升级后）:

```markdown
---
tags: [source]
type: source
kb_id: legacy
---

# 发货时效说明

## 摘要
> LLM 生成：本文说明正常/节假日发货时效及例外情况……

## 元数据
- source_id: `物流__发货时效说明`
- type: policy
- status: succeeded
- chunks: 3

## Claims
- [[七天无理由|七天无理由]]: 运费承担方 → 买家

## 章节
- [[chunk-物流__发货时效说明-0|发货时效总则]]
- [[chunk-物流__发货时效说明-1|节假日顺延]]
```

**Entity 页**:

```markdown
# 七天无理由

## 摘要
> LLM：汇总该实体相关规则与适用范围……

## Claims
- [[source-...|发货时效说明]]: 运费承担方 → 买家
- ...

## 相关文档
- [[source-...|...]]
```

### 7.2 新增 Chunk 页（可选）

每个 chunk 独立页面 `chunk-{source_id}-{index}.md`，便于 wikilink 跳转；正文为 chunk.text + 来源链接。

### 7.3 `WikiLlmSummarizer`

```python
class WikiLlmSummarizer:
    def summarize_source(self, source, claims, chunks) -> str: ...
    def summarize_entity(self, subject, claims, related_chunks) -> str: ...
```

**缓存**:

```python
cache_key = sha256(f"{content_hash}:{prompt_version}")
# 存储于 {data_root}/{kb_id}/wiki/.cache/{hash}.txt
```

### 7.4 `export_wiki` 改造

```python
def export_wiki(..., *, use_llm: bool = False, llm_client=None, settings=None):
    ...
    if use_llm and llm_client and llm_client.is_configured:
        summary = summarizer.summarize_source(...)  # 带 cache
    else:
        summary = None  # 保持现有无摘要行为
```

CLI / Admin API:

```bash
akos wiki-export --kb legacy --with-llm-summaries
POST /admin/knowledge-bases/{kb_id}/wiki/export?use_llm=true
```

### 7.5 配置

| 变量 | 默认 | 说明 |
|------|------|------|
| `AKOS_WIKI_LLM` | `false` | 默认关闭（export 时显式开启） |
| `AKOS_WIKI_LLM_CACHE` | `true` | 摘要缓存 |
| `AKOS_WIKI_PROMPT_VERSION` | `v1` | 缓存失效版本号 |

---

## 8. 端到端数据流（完整）

```text
┌──────────────────────────────────────────────────────────────────────────┐
│ INGEST                                                                    │
├──────────────────────────────────────────────────────────────────────────┤
│ Upload → store(source + source_text)                                      │
│       → compile: Rule∪LLM → Claim + Graph + Evidence + ClaimIndex       │
│       → index_chunks: StructuralChunker → SourceChunk[] + ChunkIndex    │
│       → verify_sample                                                     │
│ Background:                                                               │
│       → enrich_source: LLM Claim 补抽                                     │
│       → enrich_chunks: LLM title/summary/topics                           │
└──────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────┐
│ ASK                                                                       │
├──────────────────────────────────────────────────────────────────────────┤
│ Question → retrieve(Claim HYBRID + Chunk search + RRF fusion)            │
│         → verify(claims) + validate(chunks)                               │
│         → explain(filter verified)                                        │
│         → synthesize(LLM + citations)  [optional]                         │
│         → answer(natural language + evidence + chunk_citations)           │
└──────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────┐
│ WIKI EXPORT                                                               │
├──────────────────────────────────────────────────────────────────────────┤
│ claims + chunks + sources → LLM summaries (cached) → markdown pages      │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 9. 分阶段实施计划

### Phase A — Chunk 基础（1–2 周）

- [ ] `SourceChunk` 模型 + `KnowledgePort` + PG 迁移
- [ ] `chunk_document()` 带 offset + 覆盖校验
- [ ] `index_chunks_node` 接入 ingest_graph
- [ ] `ChunkRetrieval`（BM25 + char-hash）
- [ ] 测试：覆盖不变量、检索命中段落

### Phase B — 双索引 Ask（1 周）

- [ ] 扩展 `Hit` / `retrieve_node` / RRF 融合
- [ ] `AskState.chunk_ids` + `Answer.chunk_citations`
- [ ] 测试：叙述性问题命中 chunk；事实问题仍命中 claim

### Phase C — LLM Synthesis（1 周）

- [ ] `synthesize_node` + prompt + citation 校验
- [ ] `answer_node` fallback 链
- [ ] LangSmith trace
- [ ] 测试：合成回答含引用；幻觉 citation 降级

### Phase D — Wiki LLM（0.5 周）

- [ ] `WikiLlmSummarizer` + cache
- [ ] CLI/API `use_llm` 参数
- [ ] chunk 子页面（可选）

### Phase E — 增强（后续）

- [ ] 真实 embedding（`AKOS_CHUNK_EMBEDDING`）
- [ ] Cross-encoder reranker
- [ ] Chunk ↔ Claim 互相链接（chunk 页展示相关 claims）

---

## 10. 风险与缓解

| 风险 | 影响 | 缓解 |
|------|------|------|
| LLM synthesis 幻觉 | 错误答案 | citation 子串校验 + 低温度 + 失败降级 |
| Chunk 过多 | 检索噪声 | RRF + top_k + summary 优先索引 |
| 上传变慢 | UX | chunk 切分同步（纯 CPU）；LLM 仅后台 |
| 存储膨胀 | PG 体积 | chunk text 可压缩；超大文档 chunk 上限 + partial |
| Wiki LLM 成本 | export 慢/贵 | content_hash 缓存 + 按需 `--with-llm` |
| 与 Claim 重复 | 答案冗余 | synthesis prompt 要求合并表述，Claim 优先于 Chunk |

---

## 11. 测试策略

| 层级 | 用例 |
|------|------|
| 单元 | `chunk_document` 覆盖不变量；RRF 融合顺序；citation 校验 |
| 集成 | 上传 → chunks 数 + 检索；ask 返回 synthesis_used |
| E2E | `samples/refund_policy_v3.md` 叙述性问题 + 事实性问题 |
| 回归 | 现有 Claim-only 测试在 `AKOS_CHUNK_INDEX=false` 下仍绿 |

---

## 12. API / 前端影响（摘要）

| 端点 | 变更 |
|------|------|
| `POST .../sources/upload` | 响应增加 `chunks_created` |
| `GET .../sources/{id}` | 可选 `chunk_count` |
| `GET .../sources/{id}/chunks` | **新增**：分页列表 chunk |
| `POST /ask` | 响应增加 `chunk_ids`, `chunk_citations`, `synthesis_used` |
| `POST .../wiki/export` | query `use_llm=true` |

---

## 13. 开放问题（评审时确认）

1. **Chunk text 是否存入 PG 还是仅 offset + 读 source_text 切片？**  
   建议：PG 存 text（检索/simple）；大文档可后续改为只存 offset。

2. **synthesis 是否允许仅 chunk 无 claim 时回答？**  
   建议：允许，但 confidence 上限 0.7，且必须 chunk citation。

3. **Wiki chunk 子页面是否默认生成？**  
   建议：Phase D 可选，默认只 source/entity 摘要。

4. **embedding 提供商？**  
   建议：Phase E；优先 OpenAI-compatible `/embeddings`。

---

**评审通过后**，按 Phase A→D 顺序实施；每 Phase 独立可交付、可回滚。
