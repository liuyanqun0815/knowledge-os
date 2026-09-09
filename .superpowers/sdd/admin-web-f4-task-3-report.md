# Admin Web F4+ Task 3 Report: Quarantine 审批页

**Status:** DONE  
**Date:** 2026-09-09  
**Commit:** `feat(web): add quarantine approval page`

## Delivered

| File | Action |
|------|--------|
| `web/src/pages/QuarantinePage.tsx` | 新建 — 隔离列表、JSON 预览、批准操作 |
| `web/src/pages/QuarantinePage.test.tsx` | 新建 — 6 个 Vitest 用例 |
| `web/src/app/router.tsx` | `/quarantine` → `QuarantinePage`；移除未用 `ComingSoonPage` 导入 |
| `web/src/components/TopNav.tsx` | 移除隔离「即将推出」标记 |

**Prerequisite (Task 1):** `web/src/api/quarantine.ts`、`types.ts` 中 `QuarantineItem` 类型。

## 功能

- 未选知识库 → `EmptyState`
- 表格列：ID、原因、原始数据（`<details>` 折叠 JSON）、操作
- 「批准」按钮 → `window.confirm` 确认 → `approveQuarantine(kbId, id)`
- 成功后刷新列表并显示 `success-banner` 提示
- 加载/列表/批准失败 → 加载态或 `ErrorBanner`
- 切换 kb 时使用 `requestSequence` 丢弃过期响应

## 测试

```bash
cd web && npm test
```

**Result:** 12 test files, 47 tests passed（含 QuarantinePage 6 项）.

## 自审

- 复用 ClaimsPage / SourcesPage 的加载与空态模式
- 批准中禁用对应行按钮，避免重复提交
- 未引入重型 UI 库；复用 `table-card` / `success-banner` 样式
