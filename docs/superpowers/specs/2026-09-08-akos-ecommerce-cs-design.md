# AKOS 电商客服知识操作系统 — 设计规格

**日期**: 2026-09-08  
**状态**: 待用户审阅  
**产品名**: Agent-Native Knowledge Operating System（AKOS）  
**首个垂直场景**: 通用企业知识 OS 内核 + 电商客服（Ecommerce CS）领域插件  
**架构选型**: 方案 B — 精简运行时 + 模块化单体（Modular Monolith）

---

## 1. 背景与目标

### 1.1 问题

传统知识库停留在 Document → Chunk → Embedding，无法稳定回答：

- 世界里发生了什么？谁参与了？
- 为什么这么判断？证据是什么？
- 可信度多少？结论现在是否仍有效？

### 1.2 产品定义

AKOS 不是 Knowledge Base，而是 Knowledge OS：知识存储 → 组织 → 推理 → 演化 → 执行形成闭环。

核心对象从 Chunk/Embedding 升级为：

`Source → Claim → Entity → Relation → Concept → Knowledge`（辅以 Event、Evidence、Memory、Ontology）

### 1.3 MVP 成功标准（一期）

> 上传一份电商退换货政策，系统抽出 Claim 并绑定证据；再问一条业务规则问题，返回结论 + 证据链 + 置信度。全程经领域模块 Port，Swagger/CLI 可复现。

一期范围：**编译入库 + 带证据问答**（A+B）。演化流水线、完整多 Agent 验证、管理台 UI 放二期（见第 9 节，规格已预先设计）。

### 1.4 非目标（一期）

- 知识演化自动 Diff 流水线（模型预留，流水线二期）
- Verification / Research 多 Agent 对抗
- Neo4j / OpenSearch（Port 预留，适配器二期）
- Procedural Memory、Web 管理台、对客机器人壳
- 完善多租户与细粒度权限

---

## 2. 总体架构

### 2.1 形态

单进程模块化单体：FastAPI 网关 + 根目录领域包。包间只通过公开 Port 交互，禁止跨包直连内部实现。

```text
                 User (CLI / Swagger)
                   │
                   ▼
          ┌─────────────────┐
          │ app / orchestrator│
          │ Main Agent        │
          └────────┬──────────┘
                   │
     ┌─────────────┼─────────────┐
     ▼             ▼             ▼
 compiler     retrieval      memory
     │             │
     ▼             ▼
 ontology ←── knowledge / graph / evidence
     ▲
     │
 domains/ecommerce_cs（领域种子注入）
     │
     ▼
   infra (PostgreSQL + pgvector + files + LLM)
```

### 2.2 根目录领域模块

```text
knowledge-os/
├── app/                      # FastAPI：路由、DI、鉴权占位
├── orchestrator/             # Main Agent：意图、编排
├── ontology/                 # 类型/关系/约束/术语归一
├── compiler/                 # Knowledge Compiler
├── knowledge/                # Source/Claim/Event/Version 真源
├── graph/                    # Entity/Relation 图运行时
├── retrieval/                # Vector + BM25 + Graph + Claim
├── evidence/                 # 结论→证据→来源
├── memory/                   # Semantic / Episodic（Procedural 二期）
├── domains/ecommerce_cs/     # 电商客服 Ontology/抽取种子
├── infra/                    # PG、文件、LLM 适配器
├── api/                      # OpenAPI 契约（可与 app 合并）
├── cli/                      # akos ingest / ask / inspect
├── tests/
└── docs/
```

### 2.3 依赖方向

```text
app / cli
  → orchestrator
      → retrieval | compiler | evidence | memory | ontology
          → knowledge | graph
              → infra

domains/ecommerce_cs → ontology（注册）, compiler（抽取提示/规则种子）
# 禁止：domains 反向依赖 orchestrator；禁止 knowledge 依赖 retrieval
```

### 2.4 一期技术选型

| 职责 | 选型 |
|------|------|
| API | FastAPI |
| 编排 | LangGraph 或等价状态机（`OrchestratorPort` 统一） |
| Source/Claim/Event/Evidence/Version | PostgreSQL |
| Embedding | pgvector |
| BM25/全文 | PostgreSQL `tsvector` |
| 图 | PostgreSQL 邻接表（或 AGE）；`GraphPort` 可换 Neo4j |
| 文件 | 本地目录 / MinIO（`FilePort`） |
| 短记忆 | PG 表；Redis 可选 |
| 语言 | Python 3.11+，black（120），snake_case |

---

## 3. 领域模块职责与 Port

### 3.1 ontology/

业务语义运行时：实体类型、谓词白名单、术语归一、Claim 校验。Agent 理解业务靠 Ontology，不靠长 Prompt。

```python
class OntologyPort(Protocol):
    def resolve_entity_type(self, mention: str) -> str | None: ...
    def allowed_predicates(self, subject_type: str, object_type: str) -> list[str]: ...
    def normalize_term(self, raw: str) -> str: ...
    def validate_claim(self, subject_type: str, predicate: str, object_type: str) -> bool: ...
```

### 3.2 compiler/

`Source` → Entity / Relation / Claim / Event → Ontology 映射 → 写入 knowledge/graph/evidence → 触发 retrieval 索引。

```python
class CompilerPort(Protocol):
    def ingest(self, source_id: str) -> CompileReport: ...
```

校验失败进入 `quarantine`，不写入主图。

### 3.3 knowledge/

结构化知识真源。Claim **追加版本，不原地覆盖**。

```python
class KnowledgePort(Protocol):
    def save_source(self, source: Source) -> Source: ...
    def append_claim(self, claim: Claim) -> Claim: ...
    def get_active_claims(self, subject: str, predicate: str | None = None) -> list[Claim]: ...
    def get_claim_history(self, claim_family_id: str) -> list[Claim]: ...
```

### 3.4 graph/

Ontology 运行时图：节点与边，不做长文本存储。

```python
class GraphPort(Protocol):
    def upsert_entity(self, entity_id: str, type: str, props: dict) -> None: ...
    def upsert_relation(self, src: str, predicate: str, dst: str, props: dict) -> None: ...
    def neighbors(self, entity_id: str, predicates: list[str] | None = None, depth: int = 1) -> list[Edge]: ...
```

### 3.5 retrieval/

混合检索；由 orchestrator 选择模式。

```python
class RetrievalPort(Protocol):
    def search(self, query: str, mode: RetrievalMode, filters: dict) -> list[Hit]: ...
    # VECTOR | BM25 | GRAPH | CLAIM | HYBRID
```

### 3.6 evidence/

答案可审计：结论 → 证据 → 来源。

```python
class EvidencePort(Protocol):
    def bind(self, claim_id: str, source_id: str, span: TextSpan, weight: float) -> None: ...
    def explain(self, claim_ids: list[str]) -> EvidenceBundle: ...
```

### 3.7 memory/

一期：Semantic + Episodic。Procedural 见二期。

```python
class MemoryPort(Protocol):
    def remember_semantic(self, key: str, value: str) -> None: ...
    def remember_episode(self, session_id: str, event: dict) -> None: ...
    def recall(self, query: str, session_id: str | None = None) -> MemoryContext: ...
```

### 3.8 orchestrator/

```python
class OrchestratorPort(Protocol):
    def ask(self, question: str, session_id: str | None = None) -> Answer: ...
    def ingest(self, file_path: str, source_type: str) -> CompileReport: ...
```

编译流与问答流分离，不共用一个僵化状态机硬耦合。

### 3.9 app/ + cli/

| 接口 | 作用 |
|------|------|
| `POST /sources` + `POST /sources/{id}/compile` | 入库并编译 |
| `POST /ask` | 问答（含 evidence） |
| `GET /claims/{id}/evidence` | 审计 |
| `akos ingest` / `akos ask` / `akos inspect` | CLI 验收 |

---

## 4. 知识模型

### 4.1 核心对象

```python
@dataclass
class Source:
    id: str
    title: str
    type: str  # policy | faq | ticket | chat_log
    uri: str
    version: str
    created_at: datetime
    status: str  # pending | ready | failed


@dataclass
class Claim:
    id: str
    family_id: str
    version: int
    subject: str
    predicate: str
    object: str
    subject_type: str
    object_type: str
    confidence: float
    status: str  # active | superseded | quarantined
    valid_from: datetime | None
    valid_to: datetime | None
    source_ids: list[str]


@dataclass
class Event:
    id: str
    type: str
    participants: list[str]
    timestamp: datetime
    source_id: str


@dataclass
class Answer:
    text: str
    claim_ids: list[str]
    evidence: list[dict]
    confidence: float
    retrieval_mode: str
```

### 4.2 PostgreSQL 表（一期）

| 表 | 用途 |
|----|------|
| `sources` | 文件元数据与版本 |
| `source_texts` | 解析全文/分片（BM25 + span） |
| `entities` | 实体节点 |
| `relations` | src / predicate / dst |
| `claims` | 主知识；family_id + version |
| `claim_evidence` | claim ↔ source ↔ span ↔ weight |
| `embeddings` | pgvector |
| `quarantine` | 编译失败 |
| `memory_episodes` | 会话情节 |
| `memory_semantics` | 语义记忆（可选） |

### 4.3 电商客服 Ontology 种子（domains/ecommerce_cs）

**实体**: Product, Category, Policy, RefundRule, ShippingRule, OrderStatus  

**关系**: 适用, 排除, 覆盖, 优先于, 引用  

**Claim 谓词白名单（MVP）**: 适用类目, 退货时限_天, 运费承担方, 需包装完好, 是否支持无理由退货  

卸载领域插件后，内核仍可将类型降为 `Concept` 入库（能力降级，不崩溃）。

---

## 5. 交互流程

### 5.1 编译流（Ingest）

```text
CLI/API → orchestrator.ingest
  → infra.files.store + knowledge.save_source
  → compiler.ingest(source_id)
      → 解析文本
      → Entity / Relation / Claim / Event 抽取
      → ontology.normalize + validate_claim
      → 通过: knowledge.append_claim
             graph.upsert_*
             evidence.bind
             retrieval.index
      → 失败: quarantine
  → CompileReport
```

示例：`退换货政策 v3.pdf` → Claim `(七天无理由, 适用类目, 非定制商品)` + PDF §2.1 span。

### 5.2 问答流（Ask）

```text
CLI/API → orchestrator.ask
  → memory.recall
  → ontology 意图/术语归一
  → 选择 RetrievalMode
  → retrieval.search
  → knowledge/graph 对齐 Claim
  → evidence.explain
  → Answer{text, claims, evidence, confidence}
  → memory.remember_episode
```

检索策略示例：

| 问题类型 | 模式 |
|----------|------|
| 退货政策是什么？ | HYBRID（VECTOR+BM25） |
| 某 SKU 是否适用运费险？ | GRAPH + CLAIM |
| 为什么不能七天无理由？ | CLAIM + Evidence |

低置信度时明确「依据不足」，禁止编造政策。

### 5.3 两流隔离

| | 编译流 | 问答流 |
|--|--------|--------|
| 写路径 | knowledge/graph/evidence/index | 基本只读；写 episode |
| 失败 | quarantine | 低置信 + 透明说明 |

---

## 6. 错误处理

| 场景 | 策略 |
|------|------|
| 文件无法解析 | Source=`failed` 或拒绝创建，返回明确错误 |
| Ontology 校验失败 | `quarantine` + CompileReport 原因 |
| LLM 超时/空结果 | 重试 1 次 → quarantine |
| 无命中/证据不足 | 低 confidence + 不编造 |
| 同 family 多条 active | 取最新 valid_from 且 confidence 最高；evidence 标注竞争结论 |
| infra 故障 | 领域错误 → API `code` + 4xx/5xx |

```python
class QuarantineError(Exception):
    def __init__(self, reason: str, raw: dict):
        self.reason = reason
        self.raw = raw
```

---

## 7. 测试与验收（一期）

1. `akos ingest samples/refund_policy_v3.pdf --type policy` → `claims_created > 0`
2. `GET /claims?subject=七天无理由` 返回结构化 Claim
3. `GET /claims/{id}/evidence` 含原文 span
4. `akos ask "定制商品能否七天无理由退货？"` → 含 claim_ids、quote、confidence
5. 无关问题 → 低置信、不编造政策
6. 单测仅 mock Port；`ecommerce_cs` 可卸载内核仍可用

---

## 8. 一期交付边界小结

| 包含 | 不包含 |
|------|--------|
| 领域模块骨架 + Port | 管理台 UI |
| PG 全存储路径 | Neo4j / OpenSearch |
| Compiler + Ask + Evidence | Evolution 自动流水线 |
| 电商 Ontology 种子 | Procedural Memory |
| CLI + Swagger | 完整多 Agent 对抗验证 |

---

## 9. 二期设计（预先规格）

二期在**不破坏一期 Port** 的前提下扩展。新增模块以根目录领域包落地；编排升级为显式多 Agent。

### 9.1 目标

1. **知识演化**：政策/FAQ 新版本自动 Diff → Claim 版本化 → 旧结论 supersede → 证据与索引更新  
2. **多 Agent 验证**：Research / Verification 降低幻觉与错误 Claim  
3. **检索引擎升级**：Neo4j、OpenSearch 可插拔  
4. **Procedural Memory**：退货/换货/投诉标准作业流程可执行指引  
5. **产品化入口**：薄管理台 + 对客/坐席问答 API 鉴权与多租户

### 9.2 二期目录增量

```text
knowledge-os/
├── evolution/                # 新增：Diff / Version / Supersede 流水线
├── agents/                   # 新增：子 Agent 实现
│   ├── retriever_agent/
│   ├── research_agent/
│   ├── verification_agent/
│   ├── memory_agent/
│   └── compiler_agent/       # 对 compiler Port 的 Agent 包装
├── graph/adapters/neo4j.py   # GraphPort 实现
├── retrieval/adapters/opensearch.py
└── admin_api/                # 可选：管理台 BFF（仍无强绑定前端框架）
```

一期 `orchestrator` 保留为门面；内部改为调度 `agents/*`。

### 9.3 知识演化系统（evolution/）

#### 9.3.1 Port

```python
@dataclass
class KnowledgeDiff:
    source_old_id: str
    source_new_id: str
    claims_added: list[str]
    claims_superseded: list[tuple[str, str]]  # (old_claim_id, new_claim_id)
    entities_changed: list[str]
    events: list[str]


class EvolutionPort(Protocol):
    def diff_sources(self, old_source_id: str, new_source_id: str) -> KnowledgeDiff: ...
    def apply_diff(self, diff: KnowledgeDiff) -> ApplyReport: ...
    def as_of(self, query_time: datetime, claim_family_id: str) -> Claim | None: ...
```

#### 9.3.2 交互流程

```text
新文件 会议纪要/政策 V2
  → compiler.ingest（产生候选 Claim，可先入 staging）
  → evolution.diff_sources(V1, V2)
      → 对齐 family（subject+predicate+object_type 或语义归一）
      → 生成 KnowledgeDiff
  → evolution.apply_diff
      → 旧 Claim.status = superseded，写 valid_to
      → 新 Claim.status = active，version = n+1
      → graph 更新边；evidence 绑定新 span
      → retrieval 再索引；旧向量标记失效或降权
      → memory：写入语义变更摘要 + Event(类型=policy_changed)
  → 可选：通知 Verification Agent 抽检高影响变更
```

示例：

```text
V1: (项目A运费险, 运费承担方, 平台)
V2: (项目A运费险, 运费承担方, 买家)
→ Claim Version 2；V1 superseded；Event: shipping_rule_changed
```

#### 9.3.3 时序查询

`as_of(t)` 支持「当时政策是什么」——问答流增加 `Time Query` 模式：`GRAPH + Evidence + Time`。

### 9.4 多 Agent 架构

```text
Main Agent (orchestrator)
    ├── Retriever Agent      # 选择并执行 RetrievalMode
    ├── Research Agent       # 多跳补全、相关政策/工单先例
    ├── Verification Agent   # 交叉验证 Claim vs 原文；冲突仲裁
    ├── Memory Agent         # 读写三类记忆
    ├── Compiler Agent       # 封装编译与 quarantine 复核
    └── Evolution Agent      # 封装 diff/apply（二期）
```

#### 9.4.1 问答流（二期增强）

```text
ask
  → Memory Agent.recall
  → Retriever Agent.search
  → Research Agent.expand（可选，复杂问题）
  → 候选 Claims
  → Verification Agent.verify
      → 抽查 evidence span 是否支持 claim
      → 冲突时降权或标 uncertain
  → Evidence.explain
  → Answer（增加 verification_status）
  → Memory Agent.remember
```

#### 9.4.2 编译流（二期增强）

```text
ingest
  → Compiler Agent
  → Ontology 校验
  → Verification Agent.sample_verify（高风险谓词全量核验）
  → 通过入库 / 失败 quarantine
  → 若 Source 标记为 replaces=old_id → Evolution Agent
```

Verification 不替代 Ontology：Ontology 管「合不合法」，Verification 管「原文是否真支持」。

### 9.5 引擎升级（适配器）

| Port | 一期 | 二期 |
|------|------|------|
| GraphPort | PG 邻接表 | Neo4j / Memgraph / Age |
| Retrieval BM25 | PG tsvector | OpenSearch |
| Memory 热数据 | PG | Redis + PG |
| Files | 本地 | MinIO 默认 |

配置切换，例如：

```text
AKOS_GRAPH_BACKEND=postgres|neo4j
AKOS_BM25_BACKEND=postgres|opensearch
```

迁移策略：双写窗口可选；默认「导出 subgraph → 导入 Neo4j → 切读」。

### 9.6 Procedural Memory

```python
@dataclass
class Procedure:
    id: str
    name: str           # 如「仅退款流程」
    steps: list[Step]   # 条件、动作、所需 Claim/证据
    ontology_refs: list[str]


class MemoryPort(Protocol):  # 二期扩展方法
    def remember_procedure(self, procedure: Procedure) -> None: ...
    def get_procedure(self, name: str) -> Procedure | None: ...
```

问答/执行流可返回「下一步建议」：

```text
结论：符合仅退款
证据：...
流程：1 校验签收状态 → 2 判断原因码 → 3 创建退款单
```

一期 `MemoryPort` 保持兼容；二期用扩展接口或可选 Protocol 继承，避免破坏实现。

### 9.7 Evidence / Answer 契约扩展

```python
@dataclass
class AnswerV2:
    text: str
    claim_ids: list[str]
    evidence: list[dict]
    confidence: float
    retrieval_mode: str
    verification_status: str  # verified | partial | unverified | conflict
    as_of: datetime | None
    procedure_id: str | None
    competing_claim_ids: list[str]
```

对外 API 可用版本头或字段可选，保持一期客户端可用。

### 9.8 管理台与产品化（薄层）

| 能力 | 说明 |
|------|------|
| 源文件管理 | 上传、版本、触发 compile/evolve |
| Claim 浏览器 | 按实体/谓词筛选、历史版本时间线 |
| Quarantine 工单 | 人工确认入库或丢弃 |
| 问答调试 | 展示 RetrievalMode、Agent 轨迹 |
| 多租户 | `tenant_id` 行级隔离（表结构二期迁移） |

管理台只依赖 `admin_api` → 既有 Port，不嵌入领域逻辑。

### 9.9 二期验收标准

1. 上传政策 V2（替换 V1）→ Diff 报告正确；旧 Claim superseded；`as_of(V1时段)` 仍返回旧结论  
2. 故意植入与原文不符的 Claim → Verification Agent 拦截或标 conflict  
3. 切换 `AKOS_GRAPH_BACKEND=neo4j` 后邻居查询结果与 PG 一致（黄金集）  
4. `akos ask` 对「怎么做仅退款」返回 Procedure 步骤 + 相关 Claim 证据  
5. 管理 API 可完成：上传 → 编译 → 查看 quarantine → 问答调试

### 9.10 二期不做（更远期）

- 全自动「知识执行」对接电商 OMS/工单写操作（需强权限与人工确认闸门）
- 跨企业联邦知识、密码学级证据链
- 通用 LLM-Wiki 全民编辑前端

---

## 10. 路线图

```text
一期 MVP
  模块化单体 + PG 全栈
  Compiler + Hybrid Retrieval + Evidence Ask
  ecommerce_cs Ontology 种子
  CLI / Swagger 验收

二期
  evolution/ + agents/*
  Verification / Research
  Neo4j / OpenSearch 适配器
  Procedural Memory
  admin_api + 时序查询

远期
  Knowledge 执行闸门（工单/OMS）
  多领域插件市场（纪委、研发 Wiki 等）
```

趋势对齐（产品叙事，非实现承诺）：

```text
传统 RAG < Hybrid RAG < GraphRAG < Agentic RAG
  < Ontology KB < Knowledge OS（本项目）
```

---

## 11. 决策记录

| 决策 | 选择 | 理由 |
|------|------|------|
| 场景 | 通用内核 + 电商客服插件 | 可迁移，又有具体验收语料 |
| MVP | 编译 + 证据问答 | 先闭环再演化 |
| 入口 | 纯后端 + FastAPI/CLI | UI 不阻塞领域正确性 |
| 架构 | 模块化单体 + 精简存储 | 可落地；Port 保证可换引擎 |
| Claim | 追加版本 | 为二期演化预留，避免推倒重来 |

---

## 12. 开放问题（实现计划阶段再定）

1. 编排用 LangGraph 还是自研轻量状态机（不影响 Port）  
2. 抽取模型与提示版本管理策略  
3. Claim family 对齐：规则键 vs 嵌入聚类（二期 Diff 关键）  
4. 多租户是否在一期表结构预留 `tenant_id` 空列  

以上不影响本规格已冻结的模块边界与两期流程。
