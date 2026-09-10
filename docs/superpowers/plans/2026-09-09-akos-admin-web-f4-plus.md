# AKOS Admin Web F4+ 完善 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development

**Goal:** 解锁 Phase 2.2–2.4 后端能力的前端页面：Claim 浏览、quarantine 审批、Ask AnswerV2（verification/as_of/trace/procedure）、文档演化上传。

**Architecture:** 扩展 `web/src/api/`；新增 `ClaimsPage`、`QuarantinePage`；增强 `AskPage`、`SourcesPage`；移除顶栏「即将推出」标记。

**Spec:** `docs/superpowers/specs/2026-09-08-akos-admin-web-design.md` §3.6（F4 解锁）

**Baseline:** F0–F3 已完成；后端 admin claims/quarantine/evolution/debug 已就绪

## Global Constraints

- 只消费 HTTP JSON；显式 `knowledge_base_id`
- 中文文案；空态/加载/错误三态
- Vitest + Testing Library；每 Task commit
- 不引入重型 UI 库

---

### Task 1: API 客户端扩展

**Files:**
- Modify: `web/src/api/types.ts` — ClaimItem, QuarantineItem, AnswerV2 字段
- Create: `web/src/api/claims.ts`, `quarantine.ts`, `evolution.ts`
- Modify: `web/src/api/ask.ts` — `includeTrace` query param
- Modify: `web/src/api/sources.ts` — `uploadSource(kbId, file, { replacesSourceId? })`
- Test: `web/src/api/claims.test.ts`, `ask.test.ts` 更新

**Commit:** `feat(web): add claims quarantine and AnswerV2 API clients`

---

### Task 2: Claims 浏览页

**Files:**
- Create: `web/src/pages/ClaimsPage.tsx`, `web/src/components/ClaimHistoryPanel.tsx`
- Modify: `web/src/app/router.tsx`, `TopNav.tsx`（移除 Claim comingSoon）
- Test: `web/src/pages/ClaimsPage.test.tsx`

**功能:** status/subject 筛选；表格展示；点击 family 拉 history 侧栏/折叠

**Commit:** `feat(web): add claims browse page with history panel`

---

### Task 3: Quarantine 审批页

**Files:**
- Create: `web/src/pages/QuarantinePage.tsx`
- Modify: router, TopNav
- Test: `web/src/pages/QuarantinePage.test.tsx`

**功能:** 列表 reason/raw；approve 按钮 + confirm；成功后刷新

**Commit:** `feat(web): add quarantine approval page`

---

### Task 4: Ask 页 AnswerV2 + as_of + trace

**Files:**
- Modify: `web/src/pages/AskPage.tsx`
- Test: `web/src/pages/AskPage.test.tsx`

**功能:** datetime-local as_of；默认 `include_trace=true`；展示 verification_status、competing_claim_ids、procedure_id

**Commit:** `feat(web): enhance ask page with AnswerV2 and as_of`

---

### Task 5: 文档演化上传 + 文档收尾

**Files:**
- Modify: `web/src/pages/SourcesPage.tsx` — 可选 replaces_source_id
- Modify: `web/README.md`, 根 `README.md` — F4 验收清单

**Commit:** `feat(web): add source upload replaces and update admin web docs`

---
