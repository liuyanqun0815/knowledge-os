# 知识库详情页 Wiki 导出

**日期**: 2026-09-11  
**状态**: 已确认  

## 决策

- 入口：知识库详情页顶栏 `导出 Wiki`（整库）
- API：`POST /admin/knowledge-bases/{kb_id}/wiki/export`，默认 body
- 成功展示 `files_written` 与 `output_path`；失败用 ErrorBanner
- 非目标：Claim 页导出、自定义目录、LLM 摘要开关

## 文件

- `web/src/api/wiki.ts`
- `web/src/pages/KnowledgeBaseDetailPage.tsx`
- 相关前端测试
