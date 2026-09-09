# Admin Web F4+ Task 4 Report: Ask 页 AnswerV2 + as_of + trace

**Status:** DONE  
**Date:** 2026-09-09  
**Commit:** `feat(web): enhance ask page with AnswerV2 and as_of`

## Delivered

| File | Action |
|------|--------|
| `web/src/pages/AskPage.tsx` | 修改 — `datetime-local` as_of、默认 `includeTrace: true`、AnswerV2 元数据展示 |
| `web/src/pages/AskPage.test.tsx` | 修改 — 9 个用例（含 as_of ISO 转换、AnswerV2 字段、includeTrace 默认） |
| `web/src/styles/global.css` | 修改 — `.verification-badge-*` 四色状态样式 |

**Prerequisite (Task 1):** `web/src/api/ask.ts` 已支持 `asOf` / `includeTrace`；`AskResponse` 含 AnswerV2 字段。

## 功能

- 表单新增「截至时间（可选）」`datetime-local` 输入；提交时转为 ISO 字符串传给 `askQuestion({ asOf })`
- 每次提问默认 `includeTrace: true`，优先使用响应内 trace，否则按 `request_id` 降级拉取
- 回答卡片展示 AnswerV2 元数据：
  - **核验状态** — 彩色 badge（verified / partial / unverified / conflict）
  - **查询时点** — 格式化 `as_of`
  - **竞争 Claim** — `competing_claim_ids` 逗号分隔或「无」
  - **流程 ID** — `procedure_id` 或「—」
- 移除「时间点查询将在后续版本开放」占位文案

## 测试

```bash
cd web && npm test
```

**Result:** 12 test files, 46 tests passed（含 AskPage 9 项）.

## 自审

- `asOfLocal` 为空时不发送 `as_of` 字段，保持向后兼容
- 保留 `requestSequence` 竞态丢弃逻辑
- badge 颜色与 Phase 2.3 设计文档中 verification_status 枚举一致
