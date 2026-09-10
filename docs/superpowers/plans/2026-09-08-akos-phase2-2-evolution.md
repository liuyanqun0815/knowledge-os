# AKOS Phase 2.2 — 知识演化（evolution / as_of）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement task-by-task.

**Goal:** 政策/文档 V2 替换 V1 时自动 Diff → supersede → 索引更新；问答支持 `as_of` 时序查询与 Claim 历史时间线。

**Architecture:** 新增 `evolution/`（EvolutionPort）；编译产生 staging Claim；`ingest_graph` 在 `replaces_source_id` 存在时走 evolve 节点；`ask_graph` 增 `parse_time` + 按 `valid_from/valid_to` 过滤。

**Spec:** `docs/superpowers/specs/2026-09-08-akos-phase2-design.md` §6

**Baseline:** Phase 2.1 complete (`5d93f54`+)

## Global Constraints

- 不破坏 Phase 2.1 `knowledge_base_id` 隔离
- Claim 追加版本，禁止 UPDATE object 覆盖
- family 对齐：`sha256(subject|predicate|object_type)[:16]`（与 compiler `_family_id` 一致）
- black 120, snake_case, TDD, commit per task

---

### Task 1: evolution 模块 + KnowledgePort 扩展

**Files:** `evolution/ports.py`, `differ.py`, `applier.py`, `family.py`; extend `knowledge/ports.py`, `memory_repo.py`, `pg_repos.py` with `get_claims_for_source`, `mark_superseded`, `as_of`, `get_claims_by_status`

**Tests:** `tests/test_evolution_differ.py`, `tests/test_evolution_applier.py` (InMemory)

---

### Task 2: Source.replaces + events 表 + staging 编译

**Files:** `knowledge/models.py` (Source.replaces_source_id, Event); migration `003_evolution.sql`; `compiler/service.py` staging mode; `samples/refund_policy_v4.md`

**Tests:** `tests/test_compiler_staging.py`

---

### Task 3: LangGraph evolve 集成 ingest

**Files:** `orchestrator/state.py`, `nodes.py`, `graphs/ingest_graph.py`, `orchestrator/service.py` — `ingest(..., replaces_source_id=...)`

**Tests:** `tests/test_evolve_ingest.py`

---

### Task 4: as_of Time Query + Answer.as_of

**Files:** `orchestrator/state.py`, `nodes.py` (parse_time_node), `graphs/ask_graph.py`, `knowledge/models.py` Answer; `orchestrator/service.py` ask(..., as_of=); wire `app/routes.py`

**Tests:** `tests/test_as_of_query.py`

---

### Task 5: API + admin evolve + claim history

**Files:** `app/routes.py`, `admin_api/routes_evolution.py` or extend sources; GET claim history

**Tests:** `tests/test_evolution_api.py`

---

### Task 6: E2E v3→v4 + 验收

**Files:** `tests/test_evolution_e2e.py`, `README.md`

**验收:** v4 supersede v3 运费承担方；as_of(v3日) 仍返回买家

---
