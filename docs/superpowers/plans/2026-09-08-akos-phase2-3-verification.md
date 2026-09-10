# AKOS Phase 2.3 — 多 Agent 可信问答 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement task-by-task.

**Goal:** 引入 Verification Agent 与 AnswerV2 契约；ask/ingest LangGraph 增 verify 节点；支持 span 校验、竞争 Claim 冲突检测、LangGraph trace 调试。

**Architecture:** 新增 `agents/` 薄包装（只调 Port）；`verification_agent` 实现确定性规则；`Answer` 扩展 `verification_status` / `competing_claim_ids`；ingest 增 `verify_sample` 对高风险谓词 100% span 校验。

**Spec:** `docs/superpowers/specs/2026-09-08-akos-phase2-design.md` §7

**Baseline:** Phase 2.2 complete (`924964f`+)

## Global Constraints

- 不破坏 Phase 2.1 `knowledge_base_id` 隔离与 Phase 2.2 evolution/as_of
- 各 Agent **只调 Port**，不新增仓储逻辑
- Verification MVP 为确定性规则（子串匹配），非 LLM
- black 120, snake_case, TDD, commit per task
- ask_graph 保留 Phase 2.2 `parse_time` 节点

---

### Task 1: AnswerV2 字段 + verification 核心模块

**Files:**
- Modify: `knowledge/models.py` — Answer 增 `verification_status`, `competing_claim_ids`, `procedure_id`
- Create: `verification/ports.py`, `verification/service.py`
- Test: `tests/test_verification_service.py`

**Rules:**
1. evidence span quote 必须出现在 source_text（子串）
2. 同 family 多条 active → `conflict` + `competing_claim_ids`
3. span 不匹配 → `unverified`，confidence × 0.5
4. 全部 verified → `verified`；部分 → `partial`

**Commit:** `feat: add verification service and AnswerV2 fields`

---

### Task 2: DomainPort 高风险谓词 + ingest verify_sample

**Files:**
- Modify: `domains/base.py` — `high_risk_predicates() -> list[str]`
- Modify: `domains/ecommerce_cs/domain.py`, `domains/generic/domain.py`
- Modify: `orchestrator/state.py` (IngestState verify_report)
- Modify: `orchestrator/nodes.py` — `verify_sample_node`
- Modify: `orchestrator/graphs/ingest_graph.py` — compile → verify_sample → evolve
- Test: `tests/test_ingest_verify_sample.py`

**Commit:** `feat: add ingest verify_sample for high-risk predicates`

---

### Task 3: ask_graph verify 节点 + agents 薄包装

**Files:**
- Create: `agents/verification_agent/service.py`, `agents/retriever_agent/service.py`, etc.
- Modify: `orchestrator/state.py` — AskState: `verification`, `trace`
- Modify: `orchestrator/nodes.py` — `verify_node`, refactor retrieve via retriever_agent
- Modify: `orchestrator/graphs/ask_graph.py` — retrieve → verify → explain
- Modify: `infra/bootstrap.py` — wire VerificationService if needed
- Test: `tests/test_verify_ask.py`

**Commit:** `feat: integrate verification agent into ask LangGraph pipeline`

---

### Task 4: LangGraph trace + POST /ask 响应

**Files:**
- Modify: `orchestrator/service.py` — `ask(..., include_trace=False)` 收集节点轨迹
- Modify: `app/routes.py` — AskResponse 增 verification 字段 + trace
- Test: `tests/test_ask_trace.py`

**Commit:** `feat: expose LangGraph trace and AnswerV2 in ask API`

---

### Task 5: 冲突与 unverified E2E 验收

**Files:**
- Create: `tests/test_verification_e2e.py`
- Modify: `README.md` — Phase 2.3 验收章节

**验收 (spec §7.5):**
1. 手工注入 span 不符 Claim → `unverified` 或 quarantine
2. 竞争 Claim → `conflict` + competing_claim_ids
3. LangGraph trace JSON 可返回

**Commit:** `test: add phase 2.3 verification e2e acceptance tests`

---
