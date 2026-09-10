# AKOS Phase 2.4 — Neo4j Docker 与运营完善 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement task-by-task.

**Goal:** 生产级 Docker 部署（PG + Neo4j + MinIO + API）；Neo4j GraphPort 适配器；Procedural Memory；admin 完善（claims/quarantine/debug）；adapter parity 测试。

**Architecture:** `graph/adapters/neo4j.py` 实现 GraphPort（节点/关系带 `kb_id`）；bootstrap 按 `AKOS_GRAPH_BACKEND` 选型；Procedure 存 PG `procedures` 表；ask 检测流程问句触发 procedure。

**Spec:** `docs/superpowers/specs/2026-09-08-akos-phase2-design.md` §8

**Baseline:** Phase 2.3 complete (`4f5c48a`+)

## Global Constraints

- 图数据隔离：Neo4j 节点/关系属性 `kb_id = knowledge_base_id`；Cypher 带 `{kb_id: $kb_id}`
- 所有 admin 路由必须带 `knowledge_base_id`
- 不破坏 Phase 2.1–2.3 测试（默认 InMemory，82 passed）
- black 120, snake_case, TDD, commit per task
- neo4j 驱动为 optional dependency；集成测试 skip 若无 Neo4j

---

### Task 1: Settings + Neo4j GraphPort 适配器

**Files:**
- Create: `graph/adapters/__init__.py`, `graph/adapters/neo4j.py`
- Modify: `infra/settings.py` — `graph_backend`, `neo4j_uri`, `neo4j_user`, `neo4j_password`
- Modify: `infra/bootstrap.py` — `_build_graph()` 按 backend 选择 InMemory / PgGraph / Neo4jGraph
- Modify: `pyproject.toml` — optional `[neo4j]` extra: `neo4j>=5.0.0`
- Test: `tests/test_neo4j_graph.py` (unit with skip if no neo4j)

**Commit:** `feat: add Neo4j GraphPort adapter with kb_id isolation`

---

### Task 2: Docker Compose 生产部署

**Files:**
- Create: `deploy/docker-compose.yml`, `deploy/docker-compose.dev.yml`, `deploy/.env.production.example`, `Dockerfile`
- Modify: `.env.example` — graph/files backend vars
- Optional: `deploy/init-db.sh` or document schema apply in README

**Services:** postgres, neo4j, minio, redis(optional), akos-api

**Commit:** `feat: add docker-compose production stack`

---

### Task 3: Procedural Memory

**Files:**
- Create: `memory/models.py` (Procedure, Step)
- Modify: `memory/ports.py` — `remember_procedure`, `get_procedure`
- Modify: `memory/memory_repo.py`, `infra/pg_memory.py`
- Create: `infra/migrations/004_procedures.sql`
- Modify: `orchestrator/nodes.py` — procedure detection in route_mode or answer; set `Answer.procedure_id`
- Seed sample procedure for ecommerce refund flow in `domains/ecommerce_cs/seed.py` or bootstrap
- Test: `tests/test_procedure_memory.py`

**Commit:** `feat: add procedural memory and ask procedure routing`

---

### Task 4: admin_api 完善

**Files:**
- Create: `admin_api/routes_claims.py`, `admin_api/routes_quarantine.py`, `admin_api/routes_debug.py`
- Modify: `knowledge/ports.py` + repos — `remove_quarantine`, `approve_quarantine_item` (create active claim from raw)
- Modify: `app/main.py` — register routers
- Test: `tests/test_admin_phase24.py`

**Commit:** `feat: extend admin API for claims quarantine and debug`

---

### Task 5: Adapter parity + CLI

**Files:**
- Create: `tests/test_adapter_parity.py` — InMemory vs PgGraph golden set; Neo4j skip unless env
- Modify: `cli/main.py` — ask output includes verification_status, procedure_id

**Commit:** `test: add graph adapter parity tests and CLI AnswerV2 fields`

---

### Task 6: Phase 2.4 E2E + README

**Files:**
- Create: `tests/test_phase24_e2e.py`
- Modify: `README.md` — Phase 2.4 docker + acceptance

**验收 (spec §8.4):**
1. docker compose 文档与配置就绪
2. admin 全链路（create kb → upload → compile → ask）
3. procedure 问句返回 steps
4. quarantine approve 进入主图

**Commit:** `test: add phase 2.4 e2e acceptance tests`

---
