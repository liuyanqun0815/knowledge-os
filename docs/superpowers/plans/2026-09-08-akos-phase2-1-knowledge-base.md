# AKOS Phase 2.1 — 知识库 + 平台化基础 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 落地通用生产平台基础——知识库 CRUD、按库隔离数据、admin 上传维护、问答/API/CLI 必须指定 `knowledge_base_id`，PG 全栈持久化修复跨命令 CLI。

**Architecture:** 新增 `knowledge_base/` 模块与 `KnowledgeBasePort`；所有仓储查询 scoped by `knowledge_base_id`；`build_orchestrator_for_kb(kb_id)` 按库的 `domain_type` 加载 `DomainPort`；`admin_api` 负责建库与上传；一期 e2e 通过 fixture 种子库 `test-ecommerce` 保持兼容。

**Tech Stack:** Python 3.11+、FastAPI、LangGraph、PostgreSQL、SQLAlchemy 2.x、Typer、pytest、black（120）

**Spec:** `docs/superpowers/specs/2026-09-08-akos-phase2-design.md` §5（Phase 2.1）

**Out of scope（本计划不做，见 Phase 2.2–2.4 独立 plan）:** evolution/、Verification Agent、Neo4j Docker、LlmExtractor 生产调优、Web 管理台 UI

## Global Constraints

- Python 3.11+；black max_line_length=120；禁止 `from module import *`；snake_case
- **隔离键为 `knowledge_base_id`，禁止 `tenant_id`**
- `POST /ask` **必须** body 含 `knowledge_base_id`
- 领域由知识库 `domain_type` 决定，生产不用 `AKOS_DOMAIN` 切域
- 开发/CI 可保留 `AKOS_USE_PG=false` + InMemory；生产文档要求 `AKOS_USE_PG=true`
- OpenAI 兼容 LLM 配置预留（`AKOS_LLM_*`），2.1 仅 stub，不阻塞验收
- 每个 Task 结束：相关测试 PASS + git commit
- 不破坏一期 Port 签名扩展方式：增参数/新方法，deprecated 旧 bootstrap 路径需测试兼容

---

## File Structure (Phase 2.1)

```text
knowledge-os/
├── knowledge_base/
│   ├── __init__.py
│   ├── models.py              # KnowledgeBase dataclass
│   ├── ports.py               # KnowledgeBasePort
│   └── pg_repo.py             # PgKnowledgeBaseRepo
├── domains/
│   ├── base.py                # DomainPort Protocol
│   ├── registry.py            # load_domain(domain_type)
│   ├── ecommerce_cs/
│   │   ├── domain.py          # EcommerceCsDomain implements DomainPort
│   │   ├── seed.py            # 保留，由 domain 调用
│   │   └── formatter.py
│   ├── corporate_culture/
│   │   └── domain.py          # skeleton + generic ontology seed
│   ├── loan_finance/
│   │   └── domain.py          # skeleton
│   └── generic/
│       └── domain.py
├── infra/
│   ├── migrations/
│   │   └── 002_knowledge_bases.sql
│   ├── pg_graph.py
│   ├── pg_evidence.py
│   ├── pg_memory.py
│   └── bootstrap.py           # build_orchestrator_for_kb
├── admin_api/
│   ├── __init__.py
│   ├── routes_knowledge_bases.py
│   └── routes_sources.py
├── orchestrator/
│   ├── ports.py               # 增 ask(kb_id, ...)
│   ├── nodes.py               # 使用 deps.domain
│   └── service.py
├── app/routes.py                # AskRequest + kb_id
├── cli/main.py                  # --kb
└── tests/
    ├── conftest.py              # pg fixture + seed test-ecommerce kb
    ├── test_knowledge_base.py
    ├── test_domain_port.py
    ├── test_kb_isolation.py
    ├── test_admin_kb_api.py
    └── test_cli_kb_persistence.py
```

---

### Task 1: KnowledgeBase 模型与 Port

**Files:**
- Create: `knowledge_base/models.py`, `knowledge_base/ports.py`, `knowledge_base/pg_repo.py`
- Create: `infra/migrations/002_knowledge_bases.sql`
- Test: `tests/test_knowledge_base.py`

**Interfaces:**
- Consumes: 无
- Produces: `KnowledgeBase`; `KnowledgeBasePort` with `create`, `get`, `list`, `update`, `archive`

- [ ] **Step 1: Write migration + failing test**

`infra/migrations/002_knowledge_bases.sql`（见 spec §5.3，含 `knowledge_bases` 表）。

```python
# tests/test_knowledge_base.py
from datetime import datetime, timezone

import pytest

pytestmark = pytest.mark.skipif(
    not _pg_enabled(),
    reason="requires AKOS_USE_PG=true",
)


def test_create_and_get_knowledge_base(pg_kb_repo):
    kb = pg_kb_repo.create(name="测试库", domain_type="ecommerce_cs", description="")
    loaded = pg_kb_repo.get(kb.id)
    assert loaded.name == "测试库"
    assert loaded.domain_type == "ecommerce_cs"
    assert loaded.status == "active"
```

- [ ] **Step 2: Run test — expect FAIL**

Run: `AKOS_USE_PG=true pytest tests/test_knowledge_base.py -v`

- [ ] **Step 3: Implement**

```python
# knowledge_base/models.py
@dataclass
class KnowledgeBase:
    id: str
    name: str
    domain_type: str
    description: str
    status: str
    created_at: datetime
    updated_at: datetime
```

`PgKnowledgeBaseRepo`：UUID id；`create/get/list/update/archive`。

- [ ] **Step 4: Run test — PASS**

- [ ] **Step 5: Commit**

```bash
git commit -m "feat: add knowledge base model and PostgreSQL repository"
```

---

### Task 2: 业务表 knowledge_base_id 迁移 + PgKnowledge 作用域

**Files:**
- Modify: `infra/migrations/002_knowledge_bases.sql`（追加 ALTER 各表）
- Modify: `infra/pg_repos.py` → `PgKnowledge(engine, knowledge_base_id: str)`
- Modify: `knowledge/ports.py`（方法签名文档化 kb 由 repo 构造注入）
- Test: `tests/test_kb_isolation.py`

**Interfaces:**
- Consumes: `KnowledgeBasePort`, `PgKnowledge`
- Produces: `PgKnowledge(kb_id)` 所有 INSERT/SELECT 带 `WHERE knowledge_base_id = :kb_id`

- [ ] **Step 1: Write failing isolation test**

```python
def test_two_kbs_claims_do_not_leak(pg_kb_repo, pg_engine):
    kb_a = pg_kb_repo.create(name="A", domain_type="ecommerce_cs", description="")
    kb_b = pg_kb_repo.create(name="B", domain_type="ecommerce_cs", description="")
    repo_a = PgKnowledge(pg_engine, kb_a.id)
    repo_b = PgKnowledge(pg_engine, kb_b.id)
    # save claim only in A
    repo_a.append_claim(_sample_claim(source_ids=["s1"]))
    assert repo_a.get_active_claims("七天无理由")
    assert not repo_b.get_active_claims("七天无理由")
```

- [ ] **Step 2–4: Implement scoped PgKnowledge; migration adds kb_id columns**

- [ ] **Step 5: Commit**

```bash
git commit -m "feat: scope PostgreSQL knowledge repository by knowledge_base_id"
```

---

### Task 3: DomainPort + 领域注册表

**Files:**
- Create: `domains/base.py`, `domains/registry.py`
- Create: `domains/ecommerce_cs/domain.py`, `formatter.py`
- Create: `domains/generic/domain.py`
- Create: `domains/corporate_culture/domain.py`, `domains/loan_finance/domain.py`（skeleton）
- Test: `tests/test_domain_port.py`

**Interfaces:**
- Produces: `load_domain("ecommerce_cs") -> DomainPort`

```python
# domains/ecommerce_cs/domain.py
class EcommerceCsDomain:
    name = "ecommerce_cs"

    def register_ontology(self, ontology: OntologyPort) -> None:
        register_ecommerce_cs(ontology)

    def get_extractor(self) -> ExtractorPort:
        return RuleExtractor()

    def get_aliases(self) -> list[str]:
        return ["7天无理由", "七天无理由退货", "无理由退货", "七天无理由"]

    def format_claim(self, claim: Claim) -> str:
        ...

    def low_confidence_message(self) -> str:
        return "依据不足，无法根据现有知识库内容回答该问题。"
```

- [ ] **Step 1: Test load_domain + format_claim for ecommerce**

- [ ] **Step 2–5: Implement; commit**

```bash
git commit -m "feat: add DomainPort registry and ecommerce domain plugin"
```

---

### Task 4: PgGraph / PgEvidence / PgMemory（kb 作用域）

**Files:**
- Create: `infra/pg_graph.py`, `infra/pg_evidence.py`, `infra/pg_memory.py`
- Modify: `infra/migrations/002_knowledge_bases.sql`
- Test: `tests/test_pg_graph_evidence_memory.py`

**Interfaces:**
- Produces: `PgGraph(kb_id)`, `PgEvidence(kb_id)`, `PgMemory(kb_id)` 实现对应 Port

- [ ] **Step 1: Tests for upsert + query scoped by kb_id**

- [ ] **Step 2–5: Implement; commit**

```bash
git commit -m "feat: add scoped PostgreSQL graph evidence and memory adapters"
```

---

### Task 5: bootstrap — build_orchestrator_for_kb

**Files:**
- Modify: `infra/bootstrap.py`, `infra/settings.py`, `.env.example`
- Modify: `orchestrator/service.py` — deps 含 `domain: DomainPort`, `knowledge_base_id: str`
- Test: update `tests/conftest.py`, `tests/test_orchestrator.py`

**Interfaces:**
- Produces: `build_orchestrator_for_kb(knowledge_base_id: str) -> LangGraphOrchestrator`
- Produces: `build_default_orchestrator()` → 使用 conftest 种子库 `test-ecommerce`（仅测试）

```python
def build_orchestrator_for_kb(knowledge_base_id: str) -> LangGraphOrchestrator:
    settings = Settings()
    kb = kb_repo.get(knowledge_base_id)
    if kb is None or kb.status != "active":
        raise DomainError("knowledge_base_not_found", {"id": knowledge_base_id})
    domain = load_domain(kb.domain_type)
    ontology = InMemoryOntology()
    domain.register_ontology(ontology)
    if settings.use_pg:
        knowledge = PgKnowledge(get_engine(), knowledge_base_id)
        graph = PgGraph(get_engine(), knowledge_base_id)
        evidence = PgEvidence(get_engine(), knowledge_base_id)
        memory = PgMemory(get_engine(), knowledge_base_id)
    else:
        knowledge = InMemoryKnowledge()
        ...
    compiler = KnowledgeCompiler(ontology, knowledge, graph, evidence, domain.get_extractor(), retrieval)
    deps = OrchestratorDeps(..., domain=domain, knowledge_base_id=knowledge_base_id)
    return LangGraphOrchestrator(deps)
```

- [ ] **Step 1: Add `OrchestratorDeps.domain` and `knowledge_base_id`**

- [ ] **Step 2: Refactor `orchestrator/nodes.py` — remove `_ALIAS_CANDIDATES`, use `deps.domain`**

- [ ] **Step 3: conftest seeds `test-ecommerce` kb when PG enabled**

- [ ] **Step 4: Full pytest PASS**

- [ ] **Step 5: Commit**

```bash
git commit -m "feat: bootstrap orchestrator per knowledge base with DomainPort"
```

---

### Task 6: 问答/API — 必须 knowledge_base_id

**Files:**
- Modify: `orchestrator/ports.py`, `orchestrator/service.py` — `ask(knowledge_base_id, question, ...)`
- Modify: `app/deps.py` — 改为 `get_kb_repo` + 按请求建 orchestrator（或 orchestrator factory）
- Modify: `app/routes.py`
- Test: `tests/test_api.py`

**Breaking change（spec 要求）:**

```python
class AskRequest(BaseModel):
    knowledge_base_id: str
    question: str
    session_id: str | None = None
```

```python
@router.post("/ask")
def ask(body: AskRequest, kb_repo=Depends(get_kb_repo)):
    orchestrator = build_orchestrator_for_kb(body.knowledge_base_id)
    answer = orchestrator.ask(body.question, session_id=body.session_id)
    ...
```

`register_source` / `compile` 同样需 `knowledge_base_id`（body 或 path prefix）。

- [ ] **Step 1: Update tests/test_api.py with kb_id from fixture**

- [ ] **Step 2–5: Implement; commit**

```bash
git commit -m "feat: require knowledge_base_id on ask and source API routes"
```

---

### Task 7: admin_api — 知识库 CRUD + 上传

**Files:**
- Create: `admin_api/routes_knowledge_bases.py`, `admin_api/routes_sources.py`
- Modify: `app/main.py` — `include_router(admin_router, prefix="/admin")`
- Test: `tests/test_admin_kb_api.py`

**Routes（spec §5.4）:**

| 方法 | 路径 |
|------|------|
| POST | `/admin/knowledge-bases` |
| GET | `/admin/knowledge-bases` |
| GET | `/admin/knowledge-bases/{id}` |
| PATCH | `/admin/knowledge-bases/{id}` |
| POST | `/admin/knowledge-bases/{id}/sources/upload` |
| GET | `/admin/knowledge-bases/{id}/sources` |

Upload 使用 `UploadFile`；存 MinIO 或 `AKOS_DATA_ROOT/{kb_id}/`（2.1 本地路径即可）；触发 `orchestrator.ingest` scoped to kb。

- [ ] **Step 1: Test create kb → upload md → list sources → claims > 0**

- [ ] **Step 2–5: Implement; commit**

```bash
git commit -m "feat: add admin API for knowledge bases and source upload"
```

---

### Task 8: CLI — --kb 与 PG 持久化

**Files:**
- Modify: `cli/main.py`
- Test: `tests/test_cli_kb_persistence.py`

```python
@app.command()
def ingest(
    path: str,
    kb: str = typer.Option(..., "--kb", help="Knowledge base id"),
    type: str = typer.Option("policy", "--type"),
):
    orchestrator = build_orchestrator_for_kb(kb)
    ...

@app.command()
def ask(
    question: str,
    kb: str = typer.Option(..., "--kb"),
    session_id: str = typer.Option("default", "--session-id"),
):
    orchestrator = build_orchestrator_for_kb(kb)
    ...
```

- [ ] **Step 1: Test — ingest in subprocess A, ask in subprocess B with same kb (PG only)**

```python
@pytest.mark.skipif(not pg_enabled, reason="needs PG")
def test_cli_cross_command_with_kb(tmp_path, seeded_kb_id):
    subprocess.run(["akos", "ingest", str(sample), "--kb", seeded_kb_id], check=True)
    r = subprocess.run(["akos", "ask", "定制商品能否七天无理由退货？", "--kb", seeded_kb_id], capture_output=True, text=True)
    assert "claim_ids" in r.stdout and "依据不足" not in json.loads(r.stdout)["text"]
```

- [ ] **Step 2–5: Implement; commit**

```bash
git commit -m "feat: add --kb flag to CLI for persistent cross-command usage"
```

---

### Task 9: LLM 配置 stub + corporate_culture skeleton 验收

**Files:**
- Create: `infra/llm.py` — `OpenAiCompatibleClient` stub（无 key 时 raise 明确错误）
- Create: `compiler/llm_extractor.py` — 骨架，2.1 仅 corporate 库可选启用
- Modify: `domains/corporate_culture/domain.py` — 最小 ontology + LlmExtractor 占位
- Modify: `.env.example`, `README.md`
- Test: `tests/test_corporate_domain_skeleton.py`

`.env.example` 增：

```text
AKOS_LLM_BASE_URL=https://api.openai.com/v1
AKOS_LLM_API_KEY=
AKOS_LLM_MODEL=gpt-4o-mini
```

2.1 验收：无 LLM key 时 corporate 上传走 generic Concept 降级或 skip；有 key 时 integration test optional。

- [ ] **Step 5: Commit + README Phase 2.1 验收命令**

```bash
git commit -m "docs: add Phase 2.1 env config and corporate culture domain skeleton"
```

---

### Task 10: 一期 e2e 兼容 + 全量回归

**Files:**
- Modify: `tests/test_e2e_sample.py`, `tests/conftest.py`
- Modify: `README.md`

- [x] **Step 1: e2e 使用 `seeded_kb_id`（PG 种子库 `test-ecommerce`）**

```python
@pytest.fixture(scope="session")
def seeded_kb_id(request):
    if not pg_enabled():
        return "default"
    pg_kb_repo = request.getfixturevalue("pg_kb_repo")
    kb = pg_kb_repo.create(name="test-ecommerce", domain_type="ecommerce_cs", description="ci")
    return kb.id

def test_mvp_success_criterion(seeded_kb_id):
    orch = build_orchestrator_for_kb(seeded_kb_id)
    ...
```

- [x] **Step 2: `pytest -v` 全绿；InMemory 模式 skip PG-only tests**

- [x] **Step 3: Commit**

```bash
git commit -m "test: adapt phase-1 e2e to knowledge base scoped orchestrator"
```

---

## Phase 2.1 验收清单（对照 spec §5.5）

- [ ] admin 创建 `corporate_culture` 库 + 上传 → claims > 0  
- [ ] 两个库 Claim 互不可见（`test_kb_isolation`）  
- [ ] `POST /ask` 带 `knowledge_base_id` 只命中该库  
- [ ] `akos ask --kb <id>` 跨命令可答（PG）  
- [x] 一期 e2e 在 `test-ecommerce` 库 PASS  

---

## Spec Coverage（2.1）

| Spec §5 要求 | Task |
|--------------|------|
| KnowledgeBase 模型 | 1 |
| kb_id 全表隔离 | 2, 4 |
| DomainPort + registry | 3 |
| PG 全栈 | 2, 4 |
| bootstrap per kb | 5 |
| ask 必须 kb_id | 6 |
| admin CRUD + upload | 7 |
| CLI --kb | 8 |
| LLM env stub | 9 |
| e2e 兼容 | 10 |

---

## 后续计划（独立 plan，不在本文件执行）

| Plan 文件（待写） | 内容 |
|-------------------|------|
| `2026-09-08-akos-phase2-2-evolution.md` | evolution/、as_of、Time Query |
| `2026-09-08-akos-phase2-3-agents.md` | Verification/Research、AnswerV2 |
| `2026-09-08-akos-phase2-4-docker-neo4j.md` | docker-compose、Neo4j、MinIO、Procedure |

---

## 执行方式

Plan complete and saved to `docs/superpowers/plans/2026-09-08-akos-phase2-1-knowledge-base.md`.

**Two execution options:**

1. **Subagent-Driven（推荐）** — 每 Task 独立 subagent  
2. **Inline Execution** — 本会话连续执行  

**Which approach?**
