# AKOS Phase-1 MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 落地一期闭环——上传电商退换货政策文本，编译出 Claim 并绑定证据；问答返回结论 + 证据链 + 置信度（CLI/Swagger 可复现）。

**Architecture:** 根目录领域模块的模块化单体；包间只经 Port 交互。**编排层锁定 LangGraph**：`ingest_graph` / `ask_graph` 两条 `StateGraph`，`OrchestratorPort` 作门面。单元测试默认 InMemory 适配器；PostgreSQL + pgvector 作为可切换生产适配器。抽取层先用确定性 `RuleExtractor`（保证无 LLM Key 也能验收），再挂可选 `LlmExtractor`。

**Tech Stack:** Python 3.11+、**LangGraph**、langchain-core、FastAPI、Typer CLI、pytest、PostgreSQL、pgvector、SQLAlchemy 2.x、black（max_line_length=120）

**Spec:** `docs/superpowers/specs/2026-09-08-akos-ecommerce-cs-design.md`

**Out of scope（本计划不做，二期另开 plan）:** evolution/、多 Agent Verification/Research、Neo4j/OpenSearch、Procedural Memory、管理台 UI

## Global Constraints

- Python 3.11+；强制 black（max_line_length=120）；禁止 `from module import *`；snake_case
- 依赖方向：`app/cli → orchestrator → {compiler,retrieval,evidence,memory,ontology} → {knowledge,graph} → infra`；`domains/ecommerce_cs` 只注入 ontology/compiler
- **编排必须用 LangGraph `StateGraph`**：`orchestrator/graphs/` 定义 ingest/ask 双图；节点只调 Port，不直连仓储内部
- Claim **追加版本，禁止原地覆盖**；校验失败进 quarantine，不入主图
- 低置信问答必须标明依据不足，禁止编造政策
- 每个 Task 结束必须：测试通过 + git commit

---

## File Structure (锁定)

```text
knowledge-os/
├── pyproject.toml
├── README.md
├── .env.example
├── samples/
│   └── refund_policy_v3.md
├── knowledge/
│   ├── __init__.py
│   ├── models.py              # Source, Claim, Event, Answer, TextSpan, ...
│   ├── ports.py               # KnowledgePort
│   ├── errors.py              # QuarantineError, DomainError
│   └── memory_repo.py         # InMemoryKnowledge
├── ontology/
│   ├── __init__.py
│   ├── ports.py
│   └── registry.py            # InMemoryOntology
├── graph/
│   ├── __init__.py
│   ├── ports.py               # GraphPort, Edge
│   └── memory_repo.py
├── evidence/
│   ├── __init__.py
│   ├── ports.py               # EvidencePort, EvidenceBundle
│   └── memory_repo.py
├── memory/
│   ├── __init__.py
│   ├── ports.py
│   └── memory_repo.py
├── retrieval/
│   ├── __init__.py
│   ├── ports.py               # RetrievalPort, RetrievalMode, Hit
│   └── hybrid.py
├── compiler/
│   ├── __init__.py
│   ├── ports.py               # CompilerPort, CompileReport, ExtractorPort
│   ├── rule_extractor.py
│   └── service.py
├── orchestrator/
│   ├── __init__.py
│   ├── ports.py               # OrchestratorPort
│   ├── service.py             # LangGraphOrchestrator 门面
│   ├── state.py               # IngestState / AskState TypedDict
│   ├── nodes.py               # 图节点（只调 Port）
│   └── graphs/
│       ├── __init__.py
│       ├── ingest_graph.py    # store → compile
│       └── ask_graph.py       # recall → … → remember
├── domains/
│   └── ecommerce_cs/
│       ├── __init__.py
│       └── seed.py
├── infra/
│   ├── __init__.py
│   ├── files.py               # LocalFileStore
│   ├── settings.py
│   ├── db.py                  # SQLAlchemy engine (Task 11+)
│   └── pg_repos.py            # PG adapters (Task 11+)
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── deps.py
│   └── routes.py
├── cli/
│   ├── __init__.py
│   └── main.py
└── tests/
    ├── conftest.py
    ├── test_ontology.py
    ├── test_knowledge.py
    ├── test_graph.py
    ├── test_evidence.py
    ├── test_compiler.py
    ├── test_retrieval.py
    ├── test_memory.py
    ├── test_orchestrator.py
    ├── test_orchestrator_graph.py
    ├── test_api.py
    └── test_e2e_sample.py
```

---

### Task 1: 工程脚手架

**Files:**
- Create: `pyproject.toml`
- Create: `README.md`
- Create: `knowledge/__init__.py`（空包占位可与 Task 2 合并创建）
- Create: `tests/conftest.py`
- Test: `tests/test_scaffold.py`

**Interfaces:**
- Consumes: 无
- Produces: 可安装的 `akos` 包布局；`pytest` 可运行

- [ ] **Step 1: Write the failing test**

```python
# tests/test_scaffold.py
def test_python_version():
    import sys

    assert sys.version_info >= (3, 11)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_scaffold.py -v`  
Expected: FAIL（项目未配置 / 无 pytest）或 collection 失败

- [ ] **Step 3: Write minimal scaffolding**

`pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "akos"
version = "0.1.0"
description = "Agent-Native Knowledge Operating System"
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
  "fastapi>=0.115.0",
  "uvicorn[standard]>=0.30.0",
  "typer>=0.12.0",
  "pydantic>=2.8.0",
  "pydantic-settings>=2.4.0",
  "sqlalchemy>=2.0.32",
  "psycopg[binary]>=3.2.0",
  "pgvector>=0.3.0",
  "httpx>=0.27.0",
  "langgraph>=0.2.0",
  "langchain-core>=0.3.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.3.0", "black>=24.8.0"]

[project.scripts]
akos = "cli.main:app"

[tool.setuptools.packages.find]
where = ["."]
include = [
  "app*", "cli*", "compiler*", "domains*", "evidence*", "graph*",
  "infra*", "knowledge*", "memory*", "ontology*", "orchestrator*", "retrieval*",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]

[tool.black]
line-length = 120
```

`README.md` 写清：安装 `pip install -e ".[dev]"`、运行 `pytest`、后续 CLI 用法占位一句话。

`tests/conftest.py`:

```python
import pytest


@pytest.fixture
def any_uuid() -> str:
    return "00000000-0000-0000-0000-000000000001"
```

创建空 `__init__.py`：`knowledge/`、`ontology/`、`graph/`、`evidence/`、`memory/`、`retrieval/`、`compiler/`、`orchestrator/`、`domains/`、`domains/ecommerce_cs/`、`infra/`、`app/`、`cli/`。

- [ ] **Step 4: Run test to verify it passes**

Run: `pip install -e ".[dev]"` 然后 `pytest tests/test_scaffold.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml README.md tests/test_scaffold.py tests/conftest.py \
  knowledge ontology graph evidence memory retrieval compiler orchestrator domains infra app cli
git commit -m "chore: scaffold AKOS modular monolith package layout"
```

---

### Task 2: 核心模型与错误类型

**Files:**
- Create: `knowledge/models.py`
- Create: `knowledge/errors.py`
- Test: `tests/test_models.py`

**Interfaces:**
- Consumes: 无
- Produces: `Source`, `Claim`, `Event`, `Answer`, `TextSpan`, `QuarantineError`, `DomainError`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_models.py
from datetime import datetime, timezone

from knowledge.errors import QuarantineError
from knowledge.models import Answer, Claim, Source, TextSpan


def test_claim_is_versioned_not_overwritten_shape():
    claim = Claim(
        id="c1",
        family_id="f1",
        version=1,
        subject="七天无理由",
        predicate="适用类目",
        object="非定制商品",
        subject_type="RefundRule",
        object_type="Category",
        confidence=0.91,
        status="active",
        valid_from=datetime.now(timezone.utc),
        valid_to=None,
        source_ids=["s1"],
    )
    assert claim.version == 1
    assert claim.status == "active"


def test_quarantine_error_carries_reason_and_raw():
    err = QuarantineError(reason="invalid_predicate", raw={"predicate": "乱写"})
    assert err.reason == "invalid_predicate"
    assert err.raw["predicate"] == "乱写"


def test_answer_and_span():
    span = TextSpan(source_id="s1", start=10, end=40, quote="定制商品不适用")
    answer = Answer(
        text="不能",
        claim_ids=["c1"],
        evidence=[{"source_id": "s1", "quote": span.quote, "weight": 0.95}],
        confidence=0.93,
        retrieval_mode="CLAIM",
    )
    assert answer.confidence == 0.93
    assert Source(
        id="s1",
        title="退换货政策v3",
        type="policy",
        uri="file://x",
        version="3",
        created_at=datetime.now(timezone.utc),
        status="ready",
    ).type == "policy"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_models.py -v`  
Expected: FAIL with `ModuleNotFoundError` or import error

- [ ] **Step 3: Write minimal implementation**

```python
# knowledge/errors.py
class DomainError(Exception):
    """Base domain error."""


class QuarantineError(DomainError):
    def __init__(self, reason: str, raw: dict):
        super().__init__(reason)
        self.reason = reason
        self.raw = raw
```

```python
# knowledge/models.py
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


@dataclass
class Source:
    id: str
    title: str
    type: str
    uri: str
    version: str
    created_at: datetime
    status: str


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
    status: str
    valid_from: Optional[datetime]
    valid_to: Optional[datetime]
    source_ids: list[str] = field(default_factory=list)


@dataclass
class Event:
    id: str
    type: str
    participants: list[str]
    timestamp: datetime
    source_id: str


@dataclass
class TextSpan:
    source_id: str
    start: int
    end: int
    quote: str


@dataclass
class Answer:
    text: str
    claim_ids: list[str]
    evidence: list[dict[str, Any]]
    confidence: float
    retrieval_mode: str
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_models.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add knowledge/models.py knowledge/errors.py tests/test_models.py
git commit -m "feat: add core knowledge models and quarantine error"
```

---

### Task 3: Ontology Port + 电商客服种子

**Files:**
- Create: `ontology/ports.py`
- Create: `ontology/registry.py`
- Create: `domains/ecommerce_cs/seed.py`
- Test: `tests/test_ontology.py`

**Interfaces:**
- Consumes: 无
- Produces: `OntologyPort`; `InMemoryOntology`; `register_ecommerce_cs(ontology) -> None`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ontology.py
from domains.ecommerce_cs.seed import register_ecommerce_cs
from ontology.registry import InMemoryOntology


def test_ecommerce_seed_validates_refund_claim():
    onto = InMemoryOntology()
    register_ecommerce_cs(onto)
    assert onto.normalize_term("7天无理由") == "七天无理由"
    assert onto.resolve_entity_type("七天无理由") == "RefundRule"
    assert onto.validate_claim("RefundRule", "适用类目", "Category") is True
    assert onto.validate_claim("RefundRule", "乱写关系", "Category") is False


def test_kernel_without_seed_degrades_to_concept():
    onto = InMemoryOntology()
    assert onto.resolve_entity_type("任意词") is None
    # 无种子时允许 Concept→任意谓词→Concept 降级策略
    assert onto.validate_claim("Concept", "相关", "Concept") is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_ontology.py -v`  
Expected: FAIL import / missing attributes

- [ ] **Step 3: Write minimal implementation**

```python
# ontology/ports.py
from typing import Protocol


class OntologyPort(Protocol):
    def resolve_entity_type(self, mention: str) -> str | None: ...
    def allowed_predicates(self, subject_type: str, object_type: str) -> list[str]: ...
    def normalize_term(self, raw: str) -> str: ...
    def validate_claim(self, subject_type: str, predicate: str, object_type: str) -> bool: ...
    def register_entity(self, mention: str, entity_type: str) -> None: ...
    def register_predicate(self, subject_type: str, predicate: str, object_type: str) -> None: ...
    def register_alias(self, alias: str, canonical: str) -> None: ...
```

```python
# ontology/registry.py
class InMemoryOntology:
    def __init__(self) -> None:
        self._types: dict[str, str] = {}
        self._aliases: dict[str, str] = {}
        self._predicates: set[tuple[str, str, str]] = set()

    def register_entity(self, mention: str, entity_type: str) -> None:
        self._types[mention] = entity_type

    def register_predicate(self, subject_type: str, predicate: str, object_type: str) -> None:
        self._predicates.add((subject_type, predicate, object_type))

    def register_alias(self, alias: str, canonical: str) -> None:
        self._aliases[alias] = canonical

    def normalize_term(self, raw: str) -> str:
        return self._aliases.get(raw, raw)

    def resolve_entity_type(self, mention: str) -> str | None:
        mention = self.normalize_term(mention)
        return self._types.get(mention)

    def allowed_predicates(self, subject_type: str, object_type: str) -> list[str]:
        return sorted({p for s, p, o in self._predicates if s == subject_type and o == object_type})

    def validate_claim(self, subject_type: str, predicate: str, object_type: str) -> bool:
        if subject_type == "Concept" and object_type == "Concept":
            return True
        return (subject_type, predicate, object_type) in self._predicates
```

```python
# domains/ecommerce_cs/seed.py
from ontology.ports import OntologyPort

ENTITY_SEEDS = {
    "七天无理由": "RefundRule",
    "非定制商品": "Category",
    "定制商品": "Category",
    "退换货政策": "Policy",
    "买家": "Concept",
    "卖家": "Concept",
    "平台": "Concept",
}

PREDICATES = [
    ("RefundRule", "适用类目", "Category"),
    ("RefundRule", "排除", "Category"),
    ("RefundRule", "退货时限_天", "Concept"),
    ("RefundRule", "运费承担方", "Concept"),
    ("RefundRule", "需包装完好", "Concept"),
    ("RefundRule", "是否支持无理由退货", "Concept"),
    ("Policy", "引用", "RefundRule"),
    ("Policy", "覆盖", "Policy"),
    ("ShippingRule", "适用", "Category"),
    ("ShippingRule", "优先于", "ShippingRule"),
]

ALIASES = {
    "7天无理由": "七天无理由",
    "七天无理由退货": "七天无理由",
    "无理由退货": "七天无理由",
}


def register_ecommerce_cs(ontology: OntologyPort) -> None:
    for mention, etype in ENTITY_SEEDS.items():
        ontology.register_entity(mention, etype)
    for s, p, o in PREDICATES:
        ontology.register_predicate(s, p, o)
    for alias, canonical in ALIASES.items():
        ontology.register_alias(alias, canonical)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_ontology.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add ontology/ domains/ecommerce_cs/ tests/test_ontology.py
git commit -m "feat: add ontology registry and ecommerce_cs seed"
```

---

### Task 4: KnowledgePort（InMemory，追加版本）

**Files:**
- Create: `knowledge/ports.py`
- Create: `knowledge/memory_repo.py`
- Test: `tests/test_knowledge.py`

**Interfaces:**
- Consumes: `Source`, `Claim`
- Produces: `KnowledgePort`; `InMemoryKnowledge` with `save_source`, `append_claim`, `get_active_claims`, `get_claim_history`, `get_source`, `save_source_text`, `get_source_text`, `add_quarantine`, `list_quarantine`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_knowledge.py
from datetime import datetime, timezone

from knowledge.memory_repo import InMemoryKnowledge
from knowledge.models import Claim, Source


def _source(sid: str = "s1") -> Source:
    return Source(
        id=sid,
        title="policy",
        type="policy",
        uri="file://p",
        version="3",
        created_at=datetime.now(timezone.utc),
        status="ready",
    )


def test_append_claim_keeps_history_and_active_filter():
    repo = InMemoryKnowledge()
    repo.save_source(_source())
    c1 = Claim(
        id="c1",
        family_id="f1",
        version=1,
        subject="七天无理由",
        predicate="运费承担方",
        object="买家",
        subject_type="RefundRule",
        object_type="Concept",
        confidence=0.9,
        status="active",
        valid_from=datetime.now(timezone.utc),
        valid_to=None,
        source_ids=["s1"],
    )
    repo.append_claim(c1)
    c2 = Claim(
        id="c2",
        family_id="f1",
        version=2,
        subject="七天无理由",
        predicate="运费承担方",
        object="平台",
        subject_type="RefundRule",
        object_type="Concept",
        confidence=0.95,
        status="active",
        valid_from=datetime.now(timezone.utc),
        valid_to=None,
        source_ids=["s1"],
    )
    # 模拟 supersede：先改旧再追加新（memory 层只存储，不自动 supersede）
    c1.status = "superseded"
    repo.append_claim(c1)
    repo.append_claim(c2)
    active = repo.get_active_claims("七天无理由", "运费承担方")
    assert len(active) == 1
    assert active[0].object == "平台"
    hist = repo.get_claim_history("f1")
    assert len(hist) >= 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_knowledge.py -v`  
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

```python
# knowledge/ports.py
from typing import Optional, Protocol

from knowledge.models import Claim, Source


class KnowledgePort(Protocol):
    def save_source(self, source: Source) -> Source: ...
    def get_source(self, source_id: str) -> Source | None: ...
    def save_source_text(self, source_id: str, text: str) -> None: ...
    def get_source_text(self, source_id: str) -> str | None: ...
    def append_claim(self, claim: Claim) -> Claim: ...
    def get_claim(self, claim_id: str) -> Claim | None: ...
    def get_active_claims(self, subject: str, predicate: str | None = None) -> list[Claim]: ...
    def get_claim_history(self, claim_family_id: str) -> list[Claim]: ...
    def add_quarantine(self, reason: str, raw: dict) -> None: ...
    def list_quarantine(self) -> list[dict]: ...
```

`knowledge/memory_repo.py`：用 dict 存 sources/texts/claims/quarantine；`append_claim` 按 `id` upsert（允许同 id 更新 status）；`get_active_claims` 过滤 `status=="active"` 且 subject/predicate 匹配。

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_knowledge.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add knowledge/ports.py knowledge/memory_repo.py tests/test_knowledge.py
git commit -m "feat: add in-memory knowledge repository with claim history"
```

---

### Task 5: GraphPort + EvidencePort（InMemory）

**Files:**
- Create: `graph/ports.py`, `graph/memory_repo.py`
- Create: `evidence/ports.py`, `evidence/memory_repo.py`
- Test: `tests/test_graph.py`, `tests/test_evidence.py`

**Interfaces:**
- Consumes: `TextSpan`, `KnowledgePort.get_claim`（evidence explain 时可只存本地绑定）
- Produces: `GraphPort`, `Edge`, `EvidencePort`, `EvidenceBundle`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_graph.py
from graph.memory_repo import InMemoryGraph


def test_upsert_and_neighbors():
    g = InMemoryGraph()
    g.upsert_entity("e_rule", "RefundRule", {"name": "七天无理由"})
    g.upsert_entity("e_cat", "Category", {"name": "非定制商品"})
    g.upsert_relation("e_rule", "适用类目", "e_cat", {})
    edges = g.neighbors("e_rule", predicates=["适用类目"], depth=1)
    assert len(edges) == 1
    assert edges[0].dst == "e_cat"
```

```python
# tests/test_evidence.py
from evidence.memory_repo import InMemoryEvidence
from knowledge.models import TextSpan


def test_bind_and_explain():
    ev = InMemoryEvidence()
    ev.bind("c1", "s1", TextSpan("s1", 0, 12, "定制商品不适用"), 0.95)
    bundle = ev.explain(["c1"])
    assert bundle.confidence >= 0.9
    assert bundle.items[0]["quote"] == "定制商品不适用"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_graph.py tests/test_evidence.py -v`  
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

```python
# graph/ports.py
from dataclasses import dataclass
from typing import Protocol


@dataclass
class Edge:
    src: str
    predicate: str
    dst: str
    props: dict


class GraphPort(Protocol):
    def upsert_entity(self, entity_id: str, type: str, props: dict) -> None: ...
    def upsert_relation(self, src: str, predicate: str, dst: str, props: dict) -> None: ...
    def neighbors(self, entity_id: str, predicates: list[str] | None = None, depth: int = 1) -> list[Edge]: ...
```

`InMemoryGraph`：`entities: dict`, `relations: list[Edge]`；neighbors 仅实现 depth=1（MVP）。

```python
# evidence/ports.py
from dataclasses import dataclass
from typing import Any, Protocol

from knowledge.models import TextSpan


@dataclass
class EvidenceBundle:
    conclusion: str
    items: list[dict[str, Any]]
    confidence: float


class EvidencePort(Protocol):
    def bind(self, claim_id: str, source_id: str, span: TextSpan, weight: float) -> None: ...
    def explain(self, claim_ids: list[str]) -> EvidenceBundle: ...
```

`InMemoryEvidence.explain`：汇总 weight 平均为 confidence；`conclusion` 暂用 `"; ".join(claim_ids)`（Orchestrator 再生成自然语言）。

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_graph.py tests/test_evidence.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add graph/ evidence/ tests/test_graph.py tests/test_evidence.py
git commit -m "feat: add in-memory graph and evidence engines"
```

---

### Task 6: RuleExtractor + Compiler 服务

**Files:**
- Create: `compiler/ports.py`
- Create: `compiler/rule_extractor.py`
- Create: `compiler/service.py`
- Create: `infra/files.py`
- Create: `samples/refund_policy_v3.md`
- Test: `tests/test_compiler.py`

**Interfaces:**
- Consumes: `OntologyPort`, `KnowledgePort`, `GraphPort`, `EvidencePort`；后续 Task 7 的 `RetrievalPort.index`
- Produces: `CompilerPort.ingest(source_id) -> CompileReport`；`ExtractorPort.extract(text) -> list[ExtractedClaim]`

**Compile 时检索索引：** 本 Task 注入可选 `indexer: RetrievalPort | None`；为 `None` 则跳过 index（Task 7 补上后由 Orchestrator 注入）。

- [ ] **Step 1: Write sample + failing test**

`samples/refund_policy_v3.md`:

```markdown
# 退换货政策 v3

## 2.1 七天无理由退货
七天无理由适用类目为非定制商品。
定制商品不适用七天无理由退货。
七天无理由退货运费承担方为买家。
```

```python
# tests/test_compiler.py
from datetime import datetime, timezone
from pathlib import Path

from compiler.rule_extractor import RuleExtractor
from compiler.service import KnowledgeCompiler
from domains.ecommerce_cs.seed import register_ecommerce_cs
from evidence.memory_repo import InMemoryEvidence
from graph.memory_repo import InMemoryGraph
from knowledge.memory_repo import InMemoryKnowledge
from knowledge.models import Source
from ontology.registry import InMemoryOntology


def test_rule_extractor_finds_claims():
    text = Path("samples/refund_policy_v3.md").read_text(encoding="utf-8")
    extracted = RuleExtractor().extract(text)
    preds = {e.predicate for e in extracted}
    assert "适用类目" in preds
    assert "排除" in preds or "是否支持无理由退货" in preds


def test_compiler_ingest_writes_claim_graph_evidence():
    onto = InMemoryOntology()
    register_ecommerce_cs(onto)
    knowledge = InMemoryKnowledge()
    graph = InMemoryGraph()
    evidence = InMemoryEvidence()
    src = Source(
        id="s1",
        title="退换货政策v3",
        type="policy",
        uri="samples/refund_policy_v3.md",
        version="3",
        created_at=datetime.now(timezone.utc),
        status="ready",
    )
    knowledge.save_source(src)
    knowledge.save_source_text(src.id, Path("samples/refund_policy_v3.md").read_text(encoding="utf-8"))
    compiler = KnowledgeCompiler(onto, knowledge, graph, evidence, RuleExtractor())
    report = compiler.ingest("s1")
    assert report.claims_created >= 1
    assert knowledge.get_active_claims("七天无理由")
    bundle = evidence.explain([c.id for c in knowledge.get_active_claims("七天无理由")])
    assert bundle.items
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_compiler.py -v`  
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

`compiler/ports.py` 定义：

```python
@dataclass
class ExtractedClaim:
    subject: str
    predicate: str
    object: str
    confidence: float
    quote: str
    start: int
    end: int


@dataclass
class CompileReport:
    source_id: str
    claims_created: int
    entities_upserted: int
    evidence_links: int
    quarantined: int
    errors: list[str]


class ExtractorPort(Protocol):
    def extract(self, text: str) -> list[ExtractedClaim]: ...


class CompilerPort(Protocol):
    def ingest(self, source_id: str) -> CompileReport: ...
```

`RuleExtractor`：对样本用正则/子串规则，至少抽出：

1. `七天无理由` + `适用类目` + `非定制商品`（匹配「适用类目为非定制商品」）
2. `七天无理由` + `排除` + `定制商品`（匹配「定制商品不适用」）
3. `七天无理由` + `运费承担方` + `买家`

`KnowledgeCompiler.ingest`：

1. 读 `get_source_text`；缺失则 `errors` 并 return
2. `extract`
3. 对每条：`normalize_term` → `resolve_entity_type`（None 则 `Concept`）→ `validate_claim`；失败 `add_quarantine`
4. 成功：生成 uuid、`family_id=hash(subject|predicate|object_type)`、`append_claim`、`upsert_entity/relation`、`evidence.bind`
5. 返回 `CompileReport`

`infra/files.py`：`LocalFileStore.store(path, source_type) -> tuple[uri, title, text]` 读本地 utf-8 文本（`.md/.txt`）；未知编码失败抛 `DomainError`。

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_compiler.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add compiler/ infra/files.py samples/refund_policy_v3.md tests/test_compiler.py
git commit -m "feat: add rule extractor and knowledge compiler ingest path"
```

---

### Task 7: Retrieval（CLAIM / BM25 / HYBRID）

**Files:**
- Create: `retrieval/ports.py`
- Create: `retrieval/hybrid.py`
- Test: `tests/test_retrieval.py`

**Interfaces:**
- Consumes: `KnowledgePort`, `GraphPort`
- Produces: `RetrievalPort.search` / `index_claim`；`RetrievalMode` 枚举

- [ ] **Step 1: Write the failing test**

```python
# tests/test_retrieval.py
from datetime import datetime, timezone

from domains.ecommerce_cs.seed import register_ecommerce_cs
from graph.memory_repo import InMemoryGraph
from knowledge.memory_repo import InMemoryKnowledge
from knowledge.models import Claim, Source
from ontology.registry import InMemoryOntology
from retrieval.hybrid import HybridRetrieval
from retrieval.ports import RetrievalMode


def test_claim_and_bm25_search():
    knowledge = InMemoryKnowledge()
    graph = InMemoryGraph()
    knowledge.save_source(
        Source("s1", "p", "policy", "u", "3", datetime.now(timezone.utc), "ready")
    )
    knowledge.save_source_text("s1", "七天无理由适用类目为非定制商品。定制商品不适用。")
    claim = Claim(
        id="c1",
        family_id="f1",
        version=1,
        subject="七天无理由",
        predicate="适用类目",
        object="非定制商品",
        subject_type="RefundRule",
        object_type="Category",
        confidence=0.9,
        status="active",
        valid_from=datetime.now(timezone.utc),
        valid_to=None,
        source_ids=["s1"],
    )
    knowledge.append_claim(claim)
    r = HybridRetrieval(knowledge, graph)
    r.index_claim(claim)
    hits = r.search("定制商品 七天无理由", RetrievalMode.HYBRID, {})
    assert hits
    assert any(h.claim_id == "c1" or "定制" in (h.snippet or "") for h in hits)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_retrieval.py -v`  
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

```python
# retrieval/ports.py
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from knowledge.models import Claim


class RetrievalMode(str, Enum):
    VECTOR = "VECTOR"
    BM25 = "BM25"
    GRAPH = "GRAPH"
    CLAIM = "CLAIM"
    HYBRID = "HYBRID"


@dataclass
class Hit:
    claim_id: str | None
    score: float
    snippet: str | None
    entity_id: str | None = None


class RetrievalPort(Protocol):
    def index_claim(self, claim: Claim) -> None: ...
    def search(self, query: str, mode: RetrievalMode, filters: dict) -> list[Hit]: ...
```

`HybridRetrieval`：

- `CLAIM`：active claims 的 subject/predicate/object 子串打分
- `BM25`：MVP 用简易 TF 重叠（tokenize `source_texts`），不引入 OpenSearch
- `GRAPH`：若 query 命中实体名，返回 neighbors 相关 claim（经 subject 对齐）
- `VECTOR`：一期用 bag-of-char hashing 伪向量余弦（可测、无模型依赖）；真 embedding 留给 PG 任务可选
- `HYBRID`：合并去重按 score 排序，取 top_k=5

并在 `KnowledgeCompiler` 成功写入后调用 `retrieval.index_claim`（改 `compiler/service.py` 构造函数增加 `retrieval: RetrievalPort`）。

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_retrieval.py tests/test_compiler.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add retrieval/ compiler/service.py tests/test_retrieval.py
git commit -m "feat: add hybrid retrieval with claim and lexical modes"
```

---

### Task 8: Memory + LangGraph Orchestrator（ingest/ask 双图）

**Files:**
- Create: `memory/ports.py`, `memory/memory_repo.py`
- Create: `orchestrator/ports.py`, `orchestrator/state.py`, `orchestrator/nodes.py`
- Create: `orchestrator/graphs/ingest_graph.py`, `orchestrator/graphs/ask_graph.py`
- Create: `orchestrator/service.py`（`LangGraphOrchestrator` 门面）
- Test: `tests/test_memory.py`, `tests/test_orchestrator.py`, `tests/test_orchestrator_graph.py`

**Interfaces:**
- Consumes: 前述全部 Port + `LocalFileStore`
- Produces: `OrchestratorPort`；`build_ingest_graph(deps).invoke()` / `build_ask_graph(deps).invoke()` → `Answer` / `CompileReport`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_memory.py
from memory.memory_repo import InMemoryMemoryStore


def test_episode_recall_returns_recent():
    m = InMemoryMemoryStore()
    m.remember_episode("sess1", {"q": "能否退货", "a": "看类目"})
    ctx = m.recall("退货", "sess1")
    assert ctx.episodes
```

```python
# tests/test_orchestrator_graph.py
from orchestrator.graphs.ask_graph import build_ask_graph
from orchestrator.graphs.ingest_graph import build_ingest_graph
from orchestrator.state import AskState, IngestState


def test_ingest_graph_is_langgraph_stategraph(build_orchestrator_deps):
    deps = build_orchestrator_deps()
    graph = build_ingest_graph(deps)
    assert graph.get_graph().nodes  # compiled LangGraph has nodes


def test_ask_graph_routes_low_confidence(build_orchestrator_deps):
    deps = build_orchestrator_deps()
    graph = build_ask_graph(deps)
    result: AskState = graph.invoke({"question": "今天天气怎么样？", "session_id": "s1"})
    assert result["answer"] is not None
    assert result["answer"].confidence < 0.4
```

```python
# tests/test_orchestrator.py
from pathlib import Path

from orchestrator.service import LangGraphOrchestrator
from infra.bootstrap import build_orchestrator_deps


def test_ingest_then_ask_with_evidence():
    deps = build_orchestrator_deps()
    orch = LangGraphOrchestrator(deps)
    report = orch.ingest(str(Path("samples/refund_policy_v3.md")), "policy")
    assert report.claims_created >= 1
    answer = orch.ask("定制商品能否七天无理由退货？", session_id="s1")
    assert answer.claim_ids
    assert answer.evidence
    assert answer.confidence > 0
    weak = orch.ask("今天天气怎么样？", session_id="s1")
    assert weak.confidence < 0.4
    assert "依据不足" in weak.text or "不足" in weak.text
```

`tests/conftest.py` 增加 fixture：

```python
@pytest.fixture
def build_orchestrator_deps():
    from infra.bootstrap import build_orchestrator_deps as _build
    return _build
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_memory.py tests/test_orchestrator_graph.py tests/test_orchestrator.py -v`  
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

**State（`orchestrator/state.py`）**：

```python
from typing import TypedDict, Optional
from knowledge.models import Answer
from compiler.ports import CompileReport
from retrieval.ports import Hit, RetrievalMode


class IngestState(TypedDict):
    file_path: str
    source_type: str
    source_id: str | None
    report: CompileReport | None
    error: str | None


class AskState(TypedDict):
    question: str
    session_id: str | None
    normalized_question: str | None
    retrieval_mode: RetrievalMode | None
    hits: list[Hit]
    claim_ids: list[str]
    answer: Answer | None
```

**节点（`orchestrator/nodes.py`）**：每个节点签名 `(state, deps) -> partial state`，只调 Port：

| 节点 | 职责 |
|------|------|
| `store_source_node` | `files.store` → `knowledge.save_source/text` |
| `compile_node` | `compiler.ingest(source_id)` |
| `recall_node` | `memory.recall` |
| `normalize_node` | `ontology.normalize_term` 改写问句 |
| `route_mode_node` | 规则选 `RetrievalMode`（为什么→CLAIM；关系词→GRAPH；默认 HYBRID） |
| `retrieve_node` | `retrieval.search` |
| `explain_node` | `evidence.explain(claim_ids)` |
| `answer_node` | 组装 `Answer`；无命中或 confidence&lt;0.4 → 依据不足 |
| `remember_node` | `memory.remember_episode` |

**ingest 图（`orchestrator/graphs/ingest_graph.py`）**：

```python
from langgraph.graph import END, StateGraph

from orchestrator.state import IngestState


def build_ingest_graph(deps):
    g = StateGraph(IngestState)
    g.add_node("store", lambda s: store_source_node(s, deps))
    g.add_node("compile", lambda s: compile_node(s, deps))
    g.set_entry_point("store")
    g.add_edge("store", "compile")
    g.add_edge("compile", END)
    return g.compile()
```

**ask 图（`orchestrator/graphs/ask_graph.py`）**：

```python
from langgraph.graph import END, StateGraph

from orchestrator.state import AskState


def build_ask_graph(deps):
    g = StateGraph(AskState)
    g.add_node("recall", lambda s: recall_node(s, deps))
    g.add_node("normalize", lambda s: normalize_node(s, deps))
    g.add_node("route_mode", lambda s: route_mode_node(s, deps))
    g.add_node("retrieve", lambda s: retrieve_node(s, deps))
    g.add_node("explain", lambda s: explain_node(s, deps))
    g.add_node("answer", lambda s: answer_node(s, deps))
    g.add_node("remember", lambda s: remember_node(s, deps))
    g.set_entry_point("recall")
    g.add_edge("recall", "normalize")
    g.add_edge("normalize", "route_mode")
    g.add_edge("route_mode", "retrieve")
    g.add_edge("retrieve", "explain")
    g.add_edge("explain", "answer")
    g.add_edge("answer", "remember")
    g.add_edge("remember", END)
    return g.compile()
```

**门面（`orchestrator/service.py`）**：

```python
class LangGraphOrchestrator:
    def __init__(self, deps):
        self.deps = deps
        self._ingest = build_ingest_graph(deps)
        self._ask = build_ask_graph(deps)

    def register_source(self, file_path: str, source_type: str) -> str:
        meta = self.deps.files.store(file_path, source_type)
        source = self.deps.knowledge.save_source(meta.source)
        self.deps.knowledge.save_source_text(source.id, meta.text)
        return source.id

    def compile_source(self, source_id: str) -> CompileReport:
        return self.deps.compiler.ingest(source_id)

    def ingest(self, file_path: str, source_type: str) -> CompileReport:
        state = self._ingest.invoke(
            {
                "file_path": file_path,
                "source_type": source_type,
                "source_id": None,
                "report": None,
                "error": None,
            }
        )
        return state["report"]

    def ask(self, question: str, session_id: str | None = None) -> Answer:
        state = self._ask.invoke(
            {
                "question": question,
                "session_id": session_id,
                "normalized_question": None,
                "retrieval_mode": None,
                "hits": [],
                "claim_ids": [],
                "answer": None,
            }
        )
        return state["answer"]
```

`register_source` / `compile_source` 供 API 分步调用；`ingest` = 走完整 `ingest_graph`（CLI 一键）。

`MemoryPort` / `InMemoryMemoryStore`：按 session 存 list；`recall` 返回最近 N 条 + semantic dict 命中。

**二期扩展点**：在 `ask_graph` 的 `retrieve` 与 `explain` 之间插入 `research_node` / `verify_node`，无需改 `OrchestratorPort`。

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_memory.py tests/test_orchestrator_graph.py tests/test_orchestrator.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add memory/ orchestrator/ tests/test_memory.py tests/test_orchestrator.py tests/test_orchestrator_graph.py tests/conftest.py
git commit -m "feat: add LangGraph orchestrator with ingest and ask state graphs"
```

---

### Task 9: FastAPI + Typer CLI

**Files:**
- Create: `infra/settings.py`
- Create: `app/deps.py`, `app/routes.py`, `app/main.py`
- Create: `cli/main.py`
- Test: `tests/test_api.py`

**Interfaces:**
- Consumes: `Orchestrator`
- Produces: HTTP `POST /sources`、`POST /sources/{id}/compile`、`POST /ask`、`GET /claims/{id}/evidence`；CLI `akos ingest|ask|inspect`

**说明**：`create_app()` / CLI 通过 `infra/bootstrap.py` 的 `build_default_orchestrator()` 组装 `LangGraphOrchestrator` 与 deps。

- [ ] **Step 1: Write the failing API test**

```python
# tests/test_api.py
from fastapi.testclient import TestClient

from app.main import create_app


def test_ask_endpoint_after_ingest(tmp_path):
    app = create_app(data_root=str(tmp_path))
    client = TestClient(app)
    # 复制或直接指向仓库 samples
    r = client.post(
        "/sources",
        json={"path": "samples/refund_policy_v3.md", "type": "policy"},
    )
    assert r.status_code == 200
    source_id = r.json()["source_id"]
    c = client.post(f"/sources/{source_id}/compile")
    assert c.status_code == 200
    assert c.json()["claims_created"] >= 1
    a = client.post("/ask", json={"question": "定制商品能否七天无理由退货？"})
    assert a.status_code == 200
    body = a.json()
    assert body["claim_ids"]
    assert body["evidence"]
```

说明：若希望 `POST /sources` 只注册、`compile` 分离——`Orchestrator` 可拆 `register_source`；为减少 API 表面，允许 `POST /sources` 内部只存文件+Source，`compile` 调 `compiler.ingest`。也可让 `POST /sources` 直接走完整 `ingest` 并返回 report（需同时满足路由表）。**本计划采用双端点**：`POST /sources` 存盘建 Source；`POST /sources/{id}/compile` 编译。为此给 Orchestrator 增加：

```python
def register_source(self, file_path: str, source_type: str) -> str: ...
def compile_source(self, source_id: str) -> CompileReport: ...
```

`ingest` = register + compile（CLI 一键使用）。

同步补 `tests/test_orchestrator.py` 中对 `ingest` 的覆盖即可；API 测 register+compile。

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_api.py -v`  
Expected: FAIL

- [ ] **Step 3: Write implementation**

`create_app()` 组装 InMemory 全家桶 + ecommerce seed（与测试一致）。

路由 Pydantic 模型：`AskRequest(question: str, session_id: str | None)`；响应直接 `model_dump` Answer/CompileReport。

CLI（Typer）：

```python
@app.command()
def ingest(path: str, type: str = "policy"):
    ...

@app.command()
def ask(question: str, session_id: str = "default"):
    ...

@app.command()
def inspect(claim_id: str):
    ...
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_api.py tests/test_orchestrator.py -v`  
Expected: PASS

手动：`akos ingest samples/refund_policy_v3.md`；`akos ask "定制商品能否七天无理由退货？"`

- [ ] **Step 5: Commit**

```bash
git add app/ cli/ infra/settings.py orchestrator/ tests/test_api.py
git commit -m "feat: expose FastAPI and CLI for ingest/ask/inspect"
```

---

### Task 10: 端到端验收样本 + README

**Files:**
- Modify: `README.md`
- Create: `.env.example`
- Test: `tests/test_e2e_sample.py`

**Interfaces:**
- Consumes: 全链路
- Produces: 文档化验收步骤；e2e 测试锁定成功标准

- [ ] **Step 1: Write the failing e2e test**

```python
# tests/test_e2e_sample.py
from infra.bootstrap import build_default_orchestrator


def test_mvp_success_criterion():
    orch = build_default_orchestrator()
    report = orch.ingest("samples/refund_policy_v3.md", "policy")
    assert report.claims_created > 0
    assert report.quarantined >= 0
    answer = orch.ask("定制商品能否七天无理由退货？")
    assert answer.claim_ids
    assert any("quote" in e for e in answer.evidence)
    assert 0 < answer.confidence <= 1
```

将 `build_default_orchestrator()` 放到 `infra/bootstrap.py`，`app/deps.py` 与 CLI 共用，避免重复组装。

- [ ] **Step 2: Run to verify fail/pass cycle after bootstrap extract**

Run: `pytest tests/test_e2e_sample.py -v`

- [ ] **Step 3: Update README with exact commands**

```bash
pip install -e ".[dev]"
pytest
akos ingest samples/refund_policy_v3.md --type policy
akos ask "定制商品能否七天无理由退货？"
uvicorn app.main:app --reload
```

`.env.example`:

```text
AKOS_DATA_ROOT=./data
AKOS_DATABASE_URL=postgresql+psycopg://akos:akos@localhost:5432/akos
AKOS_USE_PG=false
```

- [ ] **Step 4: Full suite**

Run: `pytest -v`  
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add README.md .env.example infra/bootstrap.py app/deps.py tests/test_e2e_sample.py
git commit -m "docs: add MVP acceptance path and e2e sample test"
```

---

### Task 11: PostgreSQL 适配器（可切换）

**Files:**
- Create: `infra/db.py`
- Create: `infra/pg_repos.py`
- Create: `infra/schema.sql`
- Modify: `infra/bootstrap.py`, `infra/settings.py`
- Test: `tests/test_pg_knowledge.py`（无数据库时 `pytest.mark.skipif`）

**Interfaces:**
- Consumes: 同 Port
- Produces: `PgKnowledge` / `PgGraph` / `PgEvidence` / `PgMemory`；`AKOS_USE_PG=true` 时 bootstrap 切换

- [ ] **Step 1: Write skip-aware test**

```python
# tests/test_pg_knowledge.py
import os

import pytest

from knowledge.models import Claim, Source

pytestmark = pytest.mark.skipif(
    os.getenv("AKOS_USE_PG", "false").lower() != "true",
    reason="AKOS_USE_PG not enabled",
)


def test_pg_append_claim_roundtrip():
    from infra.bootstrap import build_pg_knowledge
    from datetime import datetime, timezone

    repo = build_pg_knowledge()
    repo.save_source(
        Source("s-pg-1", "t", "policy", "u", "1", datetime.now(timezone.utc), "ready")
    )
    # append + get_active_claims assertions...
```

- [ ] **Step 2: Run without PG — skipped**

Run: `pytest tests/test_pg_knowledge.py -v`  
Expected: SKIPPED

- [ ] **Step 3: Implement schema + repos**

`schema.sql` 建表：`sources`, `source_texts`, `entities`, `relations`, `claims`, `claim_evidence`, `embeddings`, `quarantine`, `memory_episodes`, `memory_semantics`（字段对齐 spec 第 4.2 节）。

`PgKnowledge.append_claim` INSERT 新行；禁止 UPDATE 覆盖 object（仅允许 status/valid_to 更新用独立方法 `mark_superseded`）。

- [ ] **Step 4: Document docker one-liner in README**

```bash
docker run -d --name akos-pg -e POSTGRES_PASSWORD=akos -e POSTGRES_USER=akos -e POSTGRES_DB=akos -p 5432:5432 pgvector/pgvector:pg16
psql $AKOS_DATABASE_URL -f infra/schema.sql
AKOS_USE_PG=true pytest tests/test_pg_knowledge.py -v
```

- [ ] **Step 5: Commit**

```bash
git add infra/db.py infra/pg_repos.py infra/schema.sql infra/bootstrap.py infra/settings.py \
  tests/test_pg_knowledge.py README.md
git commit -m "feat: add PostgreSQL adapters behind existing ports"
```

---

## Spec Coverage Checklist（自审）

| Spec 要求 | Task |
|-----------|------|
| 模块化单体目录与依赖方向 | 1 |
| Source/Claim/Event/Answer/Evidence 模型 | 2 |
| Ontology + ecommerce_cs 种子 | 3 |
| Claim 追加版本 / quarantine | 4, 6 |
| Graph + Evidence | 5 |
| Compiler 抽取→校验→写入 | 6 |
| Hybrid Retrieval | 7 |
| Memory Semantic/Episodic | 8 |
| LangGraph Orchestrator（ingest/ask 双图） | 8 |
| FastAPI + CLI 验收入口 | 9 |
| MVP 成功标准 e2e | 10 |
| PostgreSQL 真源 | 11 |
| 二期 evolution/agents/Neo4j… | **不在本计划**（另开 `2026-*-akos-phase2-*.md`） |

## Placeholder / 一致性自审

- 无 TBD；Extractor 一期定为 `RuleExtractor`（可选 LLM 不阻塞验收）
- **编排锁定 LangGraph**：`orchestrator/graphs/` 双图；`LangGraphOrchestrator` 实现 `OrchestratorPort`
- `Orchestrator.register_source` / `compile_source` / `ingest` 在 Task 9 与 API 对齐
- `RetrievalPort.index_claim` 在 Task 7 引入并回写 Compiler
- VECTOR 一期为 hashing 伪向量，与 spec「pgvector」通过 Task 11 embeddings 表兼容，真模型可后续替换 `EmbedderPort`

---

## 执行方式

Plan complete and saved to `docs/superpowers/plans/2026-09-08-akos-phase1-mvp.md`.

**Two execution options:**

1. **Subagent-Driven（推荐）** — 每个 Task 派独立 subagent，任务间审查  
2. **Inline Execution** — 本会话按 executing-plans 连续执行并设检查点  

**Which approach?**
