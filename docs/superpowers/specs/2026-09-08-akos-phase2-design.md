# AKOS 二期设计规格 — 从 MVP 到可运营 Knowledge OS

**日期**: 2026-09-08  
**状态**: 已确认（2026-09-08 决策更新）；Phase 2.1 plan: `docs/superpowers/plans/2026-09-08-akos-phase2-1-knowledge-base.md`  
**依赖**: 一期 MVP（`docs/superpowers/specs/2026-09-08-akos-ecommerce-cs-design.md` §9 + 一期实现 `19da063`）  
**原则**: **不破坏一期 Port**；扩展用新包、新节点、新配置；API 向后兼容（AnswerV2 字段可选）

---

## 1. 二期动机（来自一期验证）

| 一期现象 | 根因 | 二期必须解决 |
|----------|------|--------------|
| `akos ingest` 后 `akos ask` 无答案 | CLI 每命令新建 InMemory | **默认持久化**（PG 全栈适配器） |
| 只能跑电商退换货样本 | bootstrap 写死 `ecommerce_cs` | **领域插件注册表** |
| RuleExtractor 三条正则 | MVP 确定性验收 | **LlmExtractor + 领域 ExtractorPort** |
| answer 节点写死电商谓词文案 | MVP 可读性捷径 | **DomainPort.format_claim** |
| 仅 `PgKnowledge` | 时间紧 | **PgGraph / PgEvidence / PgMemory** |
| 政策变更需人工重导 | 无 evolution | **EvolutionPort + staging** |
| 无幻觉拦截 | 无 Verification | **Verification Agent 节点** |
| 无「当时政策是什么」 | 无 as_of | **Time Query + Claim 版本链** |

---

## 2. 二期目标（可验收）

1. **通用生产平台**：内核与部署通用；业务差异通过「知识库 + 领域类型」配置，不写死单一场景  
2. **知识库隔离（非多租户）**：后台创建/维护多个知识库；问答时 **选择 knowledge_base_id**，数据按库隔离  
3. **持久化默认可用**：生产 PG 全栈 + Docker 编排；CLI/API 跨请求可问答  
4. **知识演化闭环**：Source V2 替换 V1 → Diff → supersede → 索引更新 → Event  
5. **多 Agent 增强**：LangGraph 增 Verification / Research / Evolution 节点  
6. **Neo4j 生产图引擎**：Docker 部署 Neo4j；GraphPort 适配器切换  
7. **LLM 抽取**：OpenAI 兼容 API（单一 endpoint 配置）  
8. **后台知识维护**：文档上传、编译、quarantine、演化均在 admin API 完成（不依赖预置样本文档）  
9. **Procedural Memory**：流程类问题返回步骤 + Claim 证据  

**二期成功标准（一句话）**：

> 后台创建「电商客服库」「企业文化库」两个知识库并分别上传文档；问答指定 `knowledge_base_id` 只命中该库；政策 V2 自动 supersede V1；Neo4j Docker 部署下 graph 查询正常；错误 Claim 被 Verification 标 conflict。

---

## 3. 二期范围与分期

二期拆为 **4 个可独立交付的子阶段**（建议顺序）：

```text
Phase 2.1  平台化基础     多领域 + 全 PG 持久化 + CLI 修复
Phase 2.2  知识演化       evolution/ + staging + as_of + Time Query
Phase 2.3  可信问答       agents/ + Verification/Research + AnswerV2
Phase 2.4  引擎与运营     Neo4j/OpenSearch/Redis/MinIO + admin_api + Procedure
```

| 子阶段 | 包含 | 不包含 |
|--------|------|--------|
| 2.1 | 知识库模型 + Domain 注册表、Pg 全适配、admin 上传 | 完整 LLM 抽取质量调优 |
| 2.2 | EvolutionPort、Source.replaces、staging claims | 跨 Source 自动对齐 ML 聚类 |
| 2.3 | LangGraph 增 Agent 节点、verification_status | 对抗式多轮 Research 无限扩展 |
| 2.4 | Neo4j Docker + docker-compose、admin_api 完善、Procedure | OMS 写操作（管理台 Web 见独立规格，2.1 并行） |

---

## 4. 总体架构（二期）

```text
          Admin API（知识库 CRUD、上传、quarantine、演化）
                              │
          User (CLI / 问答 API)  │  选择 knowledge_base_id
                              ▼
                    LangGraphOrchestrator（门面不变）
                              │
                   resolve_kb(kb_id) → DomainPort + 作用域过滤
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
   ingest_graph           ask_graph          evolve_graph
        │                     │                     │
   Compiler Agent      Retriever → Research    Evolution Agent
        │                     → Verify           │
        ▼                     ▼                     ▼
              Domain Plugin（按知识库 domain_type 加载）
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
   knowledge (PG)        graph (Neo4j)         retrieval
   evidence (PG)         memory (PG/Redis)     evolution
        │                     │                     │
        └─────────────────────┴─────────────────────┘
                              ▼
              docker-compose: PG + Neo4j + MinIO + (可选 Redis/OS)
```

**依赖方向（延续一期）**：

```text
app / cli / admin_api → orchestrator → agents/* → {compiler,evolution,retrieval,...}
domains/* → ontology, compiler（ExtractorPort, ClaimFormatter）
禁止 domains 依赖 orchestrator
```

---

## 5. Phase 2.1 — 平台化基础

### 5.0 知识库模型（核心，替代多租户）

**决策**：采用 **知识库（Knowledge Base）** 作为隔离单元，**不做多租户 SaaS 模型**。用户/集成方在问答时 **显式选择知识库**，后台维护各库内容与配置。

```python
@dataclass
class KnowledgeBase:
    id: str
    name: str                    # 如「电商客服-华东区」「企业文化-2026」
    domain_type: str             # ecommerce_cs | corporate_culture | loan_finance | generic
    description: str
    status: str                  # active | archived
    created_at: datetime
    updated_at: datetime
```

**隔离规则**：

- 所有 `sources`、`claims`、`entities`、`relations`、`claim_evidence`、`memory_*` 带 **`knowledge_base_id`**  
- `POST /ask` **必须**传 `knowledge_base_id`（或 slug）；检索/图查询 **仅在该库内**  
- Neo4j 节点/边属性含 `kb_id`，或按库分 label 前缀（实现细节见 2.4）  
- **禁止**用 `tenant_id` / Header 隐式切库；库选择由调用方在请求体显式指定  

**与 Domain 的关系**：

| 概念 | 职责 |
|------|------|
| `KnowledgeBase` | 数据隔离边界；一个库 = 一套文档 + Claim 集合 |
| `domain_type` | 该库使用的 Ontology + Extractor + Formatter（领域插件） |
| 生产环境 | 平台通用；创建库时选 `domain_type`，不依赖 `AKOS_DOMAIN` 环境变量 |

```python
# 问答请求（二期）
@dataclass
class AskRequest:
    knowledge_base_id: str
    question: str
    session_id: str | None = None
    as_of: datetime | None = None
```

```python
# orchestrator 解析
def ask(self, knowledge_base_id: str, question: str, ...) -> Answer:
    kb = self.kb_repo.get(knowledge_base_id)
    domain = load_domain(kb.domain_type)
    # 所有 Port 查询带 kb 作用域
    ...
```

### 5.1 领域插件模型（DomainPort）

新增 `domains/base.py`：

```python
from typing import Protocol

from compiler.ports import ExtractorPort
from ontology.ports import OntologyPort


class DomainPort(Protocol):
    name: str

    def register_ontology(self, ontology: OntologyPort) -> None: ...
    def get_extractor(self) -> ExtractorPort: ...
    def get_aliases(self) -> list[str]: ...
    def format_claim(self, claim) -> str: ...
    def low_confidence_message(self) -> str: ...
```

**领域注册表** `domains/registry.py`：

```python
DOMAIN_REGISTRY: dict[str, type[DomainPort]] = {
    "ecommerce_cs": EcommerceCsDomain,
    "corporate_culture": CorporateCultureDomain,
    "loan_finance": LoanFinanceDomain,
}


def load_domain(name: str) -> DomainPort:
    ...
```

**配置**（`infra/settings.py`）：

```text
AKOS_USE_PG=true                  # 生产必须 true
AKOS_GRAPH_BACKEND=neo4j          # 生产目标 neo4j（开发可 postgres）
AKOS_LLM_BASE_URL=...             # OpenAI 兼容 API
AKOS_LLM_API_KEY=...
AKOS_LLM_MODEL=...
AKOS_DATA_ROOT=./data             # 开发；生产 MinIO
```

**不再使用** `AKOS_DOMAIN` 作为生产切域方式；领域由 **知识库.domain_type** 决定。  
开发/单测可保留 `AKOS_DOMAIN` 作为快捷默认值（兼容一期 e2e）。

**bootstrap 改造**：

```python
def build_orchestrator_for_kb(knowledge_base_id: str) -> LangGraphOrchestrator:
    kb = kb_repo.get(knowledge_base_id)
    domain = load_domain(kb.domain_type)
    ontology = InMemoryOntology()
    domain.register_ontology(ontology)
    knowledge = PgKnowledge(engine, kb_id=knowledge_base_id)
    graph = build_graph(settings, kb_id=knowledge_base_id)
    ...
```

### 5.2 领域类型（非预置样本文档）

| domain_type | 实体示例 | 谓词示例 | Extractor |
|-------------|----------|----------|-----------|
| `ecommerce_cs` | RefundRule, Policy, Category | 适用类目, 排除, 运费承担方 | RuleExtractor + LlmExtractor |
| `corporate_culture` | Value, Behavior, Policy, Department | 倡导, 禁止, 适用于 | LlmExtractor |
| `loan_finance` | Product, RateRule, RiskLevel | 适用客户, 利率_年化, 最高额度 | LlmExtractor |
| `generic` | Concept | 相关, 定义, 属于 | LlmExtractor（降级） |

**文档来源**：全部由 **后台 admin API 上传**维护，不依赖仓库内 `samples/` 作为生产语料。  
` samples/` 仅保留 **开发/CI 测试**用途。

**从 orchestrator/nodes.py 移出**：

- `_ALIAS_CANDIDATES` → `domain.get_aliases()`  
- `_claim_to_text` 特殊分支 → `domain.format_claim(claim)`  
- 「现有政策」→ `domain.low_confidence_message()`

### 5.3 PostgreSQL 全栈适配

一期仅有 `PgKnowledge`。二期补齐：

| Port | 实现 | 表 |
|------|------|-----|
| KnowledgePort | `PgKnowledge`（已有） | sources, claims, quarantine, source_texts |
| GraphPort | `PgGraph` | entities, relations |
| EvidencePort | `PgEvidence` | claim_evidence |
| MemoryPort | `PgMemory` | memory_episodes, memory_semantics |

**bootstrap 规则**：

- `AKOS_USE_PG=true` → 四个 Port 均用 PG  
- `false` → InMemory（仅单进程/测试；README 明确 CLI 限制）

**迁移**：`infra/schema.sql` 增量 migration：

```sql
CREATE TABLE knowledge_bases (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    domain_type TEXT NOT NULL,
    description TEXT DEFAULT '',
    status TEXT DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

ALTER TABLE sources ADD COLUMN IF NOT EXISTS knowledge_base_id TEXT NOT NULL;
ALTER TABLE sources ADD COLUMN IF NOT EXISTS replaces_source_id TEXT;
ALTER TABLE claims ADD COLUMN IF NOT EXISTS knowledge_base_id TEXT NOT NULL;
ALTER TABLE claims ADD COLUMN IF NOT EXISTS staging BOOLEAN DEFAULT FALSE;
-- entities, relations, claim_evidence, memory_* 同理加 knowledge_base_id
CREATE INDEX idx_claims_kb ON claims(knowledge_base_id);
CREATE INDEX idx_sources_kb ON sources(knowledge_base_id);
```

### 5.4 admin_api — 知识库管理（2.1 即启动）

```text
admin_api/
├── routes_knowledge_bases.py   # CRUD 知识库
├── routes_sources.py           # 按库上传、列表、compile
└── routes_quarantine.py        # 按库 quarantine（2.2+ 扩展）
```

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/admin/knowledge-bases` | 创建库（name, domain_type, description） |
| GET | `/admin/knowledge-bases` | 列表 |
| GET | `/admin/knowledge-bases/{id}` | 详情 |
| PATCH | `/admin/knowledge-bases/{id}` | 更新/归档 |
| POST | `/admin/knowledge-bases/{id}/sources/upload` | 上传文件并触发 compile |
| GET | `/admin/knowledge-bases/{id}/sources` | 该库文档列表 |

### 5.5 Phase 2.1 验收

1. 后台创建 `domain_type=corporate_culture` 的知识库，上传 PDF/MD → claims > 0  
2. 创建第二个 `ecommerce_cs` 库，上传退换货政策；两库 Claim **互不可见**  
3. `POST /ask` 带 `knowledge_base_id=A` 只返回 A 库证据  
4. CLI：`akos ask --kb <id> "..."` 跨命令可答（PG 持久化）  
5. 一期 e2e 测试通过（测试库可用固定 `kb_id=test-ecommerce`）  

---

## 6. Phase 2.2 — 知识演化（evolution/）

### 6.1 模块与 Port

```text
evolution/
├── ports.py          # EvolutionPort, KnowledgeDiff, ApplyReport
├── differ.py         # diff_sources 对齐 family
├── applier.py        # apply_diff supersede + 索引
└── staging.py        # 候选 Claim 暂存区
```

```python
@dataclass
class KnowledgeDiff:
    source_old_id: str
    source_new_id: str
    claims_added: list[str]
    claims_superseded: list[tuple[str, str]]
    entities_changed: list[str]
    events: list[str]


class EvolutionPort(Protocol):
    def diff_sources(self, old_source_id: str, new_source_id: str) -> KnowledgeDiff: ...
    def apply_diff(self, diff: KnowledgeDiff) -> ApplyReport: ...
    def as_of(self, query_time: datetime, claim_family_id: str) -> Claim | None: ...
```

### 6.2 Family 对齐策略

**MVP（2.2）**：规则键

```python
family_key = f"{subject}|{predicate}|{object_type}"
```

**增强（可选）**：同 domain 内 embedding 聚类合并 family（开放项，不阻塞 2.2）。

### 6.3 交互流程

```text
POST /sources (replaces=old_id)
  → compiler.ingest → staging claims
  → evolution.diff_sources(old, new)
  → evolution.apply_diff
      → mark_superseded(old) + append_claim(new, version+1)
      → graph/evidence/retrieval 更新
      → Event(type=policy_changed)
  → ApplyReport
```

**LangGraph 新增 `evolve_graph`**（或由 ingest_graph 条件边触发）：

```text
store → compile → [replaces?] → evolve → END
```

### 6.4 Time Query

`ask_graph` 增 `parse_time_node`：

- 问句含「当时/去年/2024年」→ 解析 `as_of`  
- `retrieve` 过滤 `valid_from/valid_to`  
- `AnswerV2.as_of` 回填  

### 6.5 Phase 2.2 验收

1. `refund_policy_v3.md` → `refund_policy_v4.md`（运费承担方 买家→平台）  
2. Diff 报告 1 supersede；active claim 为新值  
3. `as_of(v3 生效日)` 仍返回「买家」  
4. `GET /claims/{family_id}/history` 时间线 2 版本  

---

## 7. Phase 2.3 — 多 Agent 可信问答

### 7.1 目录

```text
agents/
├── retriever_agent/      # 包装 retrieval + route_mode
├── research_agent/       # 多跳 graph + 相关 claim 扩展
├── verification_agent/   # span 是否支持 claim；冲突检测
├── memory_agent/         # 三类 memory 统一入口
├── compiler_agent/       # 包装 compiler + quarantine 复核
└── evolution_agent/      # 包装 evolution
```

各 Agent **只调 Port**，不新增仓储逻辑。

### 7.2 ask_graph 二期拓扑

```text
recall
  → normalize
  → route_mode
  → retrieve          (Retriever Agent)
  → research          (可选，复杂问句)
  → verify            (Verification Agent)  ← 新增
  → explain
  → answer
  → remember
```

**Verification 规则（确定性 MVP）**：

1. 每个 claim_id 的 evidence span 必须出现在 source_text 中（子串匹配）  
2. 同 family 多条 active → `competing_claim_ids` + `verification_status=conflict`  
3. span 不匹配 → `unverified`，confidence × 0.5  

### 7.3 ingest_graph 增强

```text
store → compile → verify_sample → [replaces? evolve] → END
```

高风险谓词（domain 配置）100% span 校验；失败 → quarantine。

### 7.4 AnswerV2 契约

```python
@dataclass
class AnswerV2:
    text: str
    claim_ids: list[str]
    evidence: list[dict]
    confidence: float
    retrieval_mode: str
    verification_status: str  # verified | partial | unverified | conflict
    as_of: datetime | None = None
    procedure_id: str | None = None
    competing_claim_ids: list[str] = field(default_factory=list)
```

`POST /ask` 响应增字段；旧客户端忽略新字段即可。

### 7.5 Phase 2.3 验收

1. 手工注入与原文不符的 Claim → ask 返回 `verification_status=unverified` 或 quarantine  
2. 竞争 Claim → `conflict` + 列出 competing_claim_ids  
3. LangGraph 调试 API 返回节点轨迹 JSON  

---

## 8. Phase 2.4 — Neo4j Docker 与运营完善

### 8.1 Docker 生产部署（决策：Neo4j 必上）

```text
deploy/
├── docker-compose.yml
├── docker-compose.dev.yml
└── .env.production.example
```

**docker-compose 服务**：

| 服务 | 镜像 | 用途 |
|------|------|------|
| `akos-api` | 自建 | FastAPI + LangGraph |
| `postgres` | pgvector/pgvector:pg16 | 真源 + embedding |
| `neo4j` | neo4j:5 | GraphPort 生产实现 |
| `minio` | minio/minio | 文件存储 |
| `redis` | redis:7（可选） | Memory 热读 |

```yaml
# docker-compose.yml 片段
services:
  neo4j:
    image: neo4j:5
    environment:
      NEO4J_AUTH: neo4j/akos-neo4j
    ports:
      - "7474:7474"
      - "7687:7687"
    volumes:
      - neo4j_data:/data

  akos-api:
    environment:
      AKOS_GRAPH_BACKEND: neo4j
      AKOS_NEO4J_URI: bolt://neo4j:7687
      AKOS_USE_PG: "true"
```

**图数据隔离**：Neo4j 节点/关系属性 `kb_id = knowledge_base_id`；所有 Cypher 带 `{kb_id: $kb_id}` 过滤。

**适配器**：

| 环境变量 | 生产值 | Port |
|----------|--------|------|
| `AKOS_GRAPH_BACKEND` | **neo4j** | GraphPort |
| `AKOS_BM25_BACKEND` | postgres（二期）\| opensearch（可选） | RetrievalPort |
| `AKOS_FILES_BACKEND` | **minio** | FilePort |
| `AKOS_MEMORY_HOT` | pg \| redis | MemoryPort |

**迁移**：`tests/test_adapter_parity.py` — 开发 PG 图 vs Neo4j 黄金集结果一致。

### 8.2 Procedural Memory

```python
@dataclass
class Procedure:
    id: str
    name: str
    steps: list[Step]
    ontology_refs: list[str]
    domain: str


class MemoryPort(Protocol):
    # 一期方法保留
    def remember_procedure(self, procedure: Procedure) -> None: ...
    def get_procedure(self, name: str) -> Procedure | None: ...
```

存储：PG `procedures` 表 + JSON steps。  
触发：问句含「怎么做/流程/步骤」→ `get_procedure` + 相关 Claim evidence。

### 8.3 admin_api 完善（后台维护入口）

在 2.1 知识库 CRUD + 上传基础上扩展：

```text
admin_api/
├── routes_knowledge_bases.py
├── routes_sources.py
├── routes_claims.py         # 筛选、history、staging 审批
├── routes_quarantine.py
├── routes_evolution.py      # 触发 diff/apply
└── routes_debug.py          # ask trace、graph 子图
```

**原则**：

- 所有运维操作 **必须带 knowledge_base_id**（路径或 body）  
- 无多租户 Header；单部署可多库  
- 返回 JSON；管理台 Web（React SPA）见 `docs/superpowers/specs/2026-09-08-akos-admin-web-design.md`，与 2.1 并行  
 

### 8.4 Phase 2.4 验收

1. `docker compose up` 启动 PG + Neo4j + MinIO + API  
2. 后台创建知识库 → 上传 → compile → ask（指定 kb_id）全链路  
3. Neo4j Browser 可见该库实体/关系（带 kb_id）  
4. `akos ask --kb <id> "仅退款流程怎么走？"` → procedure steps + claims  
5. quarantine 人工 approve 后进入主图  

---

## 9. 二期目录增量（汇总）

```text
knowledge-os/
├── domains/
│   ├── base.py
│   ├── registry.py
│   ├── ecommerce_cs/      #  refactor: DomainPort 实现
│   ├── corporate_culture/ #  新
│   └── loan_finance/      #  新
├── evolution/
├── agents/
│   ├── retriever_agent/
│   ├── research_agent/
│   ├── verification_agent/
│   ├── memory_agent/
│   ├── compiler_agent/
│   └── evolution_agent/
├── graph/adapters/
│   ├── postgres.py        # 从 memory_repo 演进
│   └── neo4j.py
├── retrieval/adapters/
│   └── opensearch.py
├── infra/
│   ├── pg_graph.py
│   ├── pg_evidence.py
│   ├── pg_memory.py
│   └── migrations/
├── knowledge_base/          # 新增：知识库 CRUD Port
│   ├── ports.py
│   └── pg_repo.py
├── admin_api/
└── orchestrator/graphs/
    ├── ingest_graph.py    #  增 verify / evolve 边
    ├── ask_graph.py       #  增 research / verify / time
    └── evolve_graph.py    #  新
```

---

## 10. 数据模型增量

| 表/字段 | 用途 |
|---------|------|
| **`knowledge_bases`** | 知识库元数据（name, domain_type, status） |
| `*.knowledge_base_id` | **所有业务表隔离键**（非 tenant_id） |
| `sources.replaces_source_id` | 演化链 |
| `claims.staging` | 待审批 Claim |
| `events` | policy_changed 等（含 kb_id） |
| `procedures` | Procedural Memory（含 kb_id + domain_type） |
| `agent_traces` | 调试轨迹（含 kb_id） |

---

## 11. API 增量

### 问答 API（必须选库）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/ask` | body: `{ knowledge_base_id, question, session_id?, as_of? }` → AnswerV2 |
| POST | `/sources` | body 增 `knowledge_base_id`（一期兼容：测试库默认） |

### 知识库管理（admin）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/admin/knowledge-bases` | 创建知识库 |
| GET | `/admin/knowledge-bases` | 列表 |
| GET | `/admin/knowledge-bases/{id}` | 详情 |
| PATCH | `/admin/knowledge-bases/{id}` | 更新/归档 |
| POST | `/admin/knowledge-bases/{id}/sources/upload` | 上传并 compile |
| GET | `/admin/knowledge-bases/{id}/sources` | 文档列表 |
| POST | `/admin/knowledge-bases/{id}/sources/{sid}/evolve` | diff+apply |
| GET | `/admin/knowledge-bases/{id}/claims/{family_id}/history` | 版本时间线 |
| GET | `/admin/knowledge-bases/{id}/quarantine` | quarantine 列表 |
| POST | `/admin/knowledge-bases/{id}/quarantine/{qid}/approve` | 入主图 |
| GET | `/admin/knowledge-bases/{id}/traces/{request_id}` | Agent 轨迹 |

---

## 12. 技术选型（二期）

| 组件 | 选型 | 说明 |
|------|------|------|
| 编排 | LangGraph | 增节点，不换框架 |
| 抽取 | **OpenAI 兼容 API**（已确认） | `AKOS_LLM_BASE_URL` + `AKOS_LLM_API_KEY` + `AKOS_LLM_MODEL` |
| 隔离 | **知识库 knowledge_base_id** | 非多租户 |
| 主库 | PostgreSQL + pgvector | 真源 |
| 图 | **Neo4j 5（Docker 生产）** | GraphPort 适配；开发可用 PG |
| 全文 | PostgreSQL tsvector（二期） | OpenSearch 可选后置 |
| 缓存 | Redis（可选） | Memory 热读 |
| 文件 | MinIO（Docker 生产） | admin 上传存储 |
| 部署 | **docker-compose** | PG + Neo4j + MinIO + API |

---

## 13. 已确认决策（2026-09-08）

| # | 问题 | 决策 |
|---|------|------|
| 1 | 生产环境定位 | **通用 Knowledge OS 平台**；业务通过知识库 + domain_type 配置 |
| 2 | LLM | **是**，仅 OpenAI 兼容 API（单一 endpoint） |
| 3 | Neo4j | **是**，生产 Docker 部署；`AKOS_GRAPH_BACKEND=neo4j` |
| 4 | 隔离模型 | **知识库管理**，问答时选 `knowledge_base_id`；**不做多租户** |
| 5 | 语料来源 | **后台 admin 上传维护**；不依赖预置领域样本文档 |

| 决策 | 选择 | 理由 |
|------|------|------|
| 二期默认 PG | `AKOS_USE_PG=true` 生产必须 | 修复 CLI；OS 定位 |
| 隔离单元 | knowledge_base_id | 符合「选库问答」产品模型 |
| Family 对齐 | 规则键优先 | 可测；ML 聚类后置 |
| Verification MVP | 子串匹配 | 无 LLM 也可验收 |
| 管理入口 | admin_api + 管理台 Web | Web 规格独立；API 无 SPA 硬依赖 |
| 一期 API | 字段扩展 + kb_id | 测试库兼容 e2e |

---

## 14. 二期不做（三期+）

- OMS/工单系统自动写操作（Knowledge 执行闸门）  
- 全民 Wiki / 众包编辑前端（管理台 SPA 见 `2026-09-08-akos-admin-web-design.md`）  
- 跨企业联邦知识库  

---

## 15. 路线图与工作量粗估

| 子阶段 | 核心交付 | 估时（人天） |
|--------|----------|--------------|
| 2.1 | 知识库模型 + admin 上传 + PG 全栈 + 管理台 Web F0–F3（并行） | 8–12（后端）+ 前端另计 |
| 2.2 | evolution + as_of + Time Query | 10–15 |
| 2.3 | Agents + Verification + AnswerV2 | 12–18 |
| 2.4 | **docker-compose** + Neo4j + admin 完善 + Procedure | 15–20 |
| **合计** | | **45–65** |

建议 **2.1 → 2.2 → 2.3** 为关键路径；**2.4 引擎**可与 2.3 部分并行。

---

## 16. 开放问题（已全部关闭）

所有决策见 **§13 已确认决策**。实现计划可直接基于本 spec 编写。

---

## 17. 与一期 spec §9 的关系

本文件在一期 spec 第九节基础上，按 2026-09-08 决策更新：

- **知识库模型** 替代多租户  
- **Neo4j Docker 生产** 为明确目标  
- **admin 后台上传** 为唯一生产语料入口  
- 拆分为 **2.1–2.4** 可交付子阶段  

一期 Port 与 LangGraph 双图结构 **保持不变**。
