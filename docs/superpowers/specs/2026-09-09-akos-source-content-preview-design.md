# AKOS 文档原文预览设计规格

**日期**: 2026-09-09  
**状态**: 已确认（跳过实现计划，直接开发）  
**依赖**:
- Admin Web 规格 `docs/superpowers/specs/2026-09-08-akos-admin-web-design.md`
- 现有 sources 管理 API（列表 / 上传 / 移动 / 删除）与 `SourceFileBrowser`
**原则**: 只读预览原文；不引入 Markdown 渲染库；不改变 ingest / claim 语义

---

## 1. 动机与范围

文档树已支持上传、目录浏览、移动与删除，但运营无法在页面核对 `.md` / `.txt` 原文，只能依赖「查看萃取」间接推断。需要补齐 **原文只读预览**。

### 1.1 已确认决策

| 决策 | 选择 |
|------|------|
| 展示容器 | **居中弹层**（Modal） |
| 正文格式 | **纯文本**，等宽字体原样显示（`<pre>`） |
| 打开方式 | **文件名可点** + 独立 **「查看」按钮**（两者都可） |
| API 形态 | 按 `source_id` 读取磁盘原文（方案 A） |
| 编辑 / 下载 / MD 渲染 | **不做** |

### 1.2 包含

- Admin API：按 source 返回 UTF-8 文本内容
- 文档来源页（及知识库详情中复用的文件浏览器，若共用组件）：弹层预览
- 超限与缺失文件的明确错误提示

### 1.3 不包含

- 在线编辑、保存回写
- Markdown / HTML 渲染与切换源码
- 下载附件、打印
- 按相对路径直接读未入库文件
- 文件夹预览

---

## 2. 后端 API

### 2.1 端点

```http
GET /admin/knowledge-bases/{kb_id}/sources/{source_id}/content
```

鉴权与其它 admin sources 路由一致（可选 `X-Admin-Token`）。

### 2.2 成功响应 `200`

```json
{
  "source_id": "policies__refund",
  "title": "refund.md",
  "relative_path": "policies/refund.md",
  "content": "# 退款政策\n...",
  "size_bytes": 1234,
  "encoding": "utf-8"
}
```

### 2.3 错误

| 状态 | 条件 |
|------|------|
| `404` | KB / source 不存在，或磁盘文件缺失 |
| `413` | 文件大小超过上限（默认 **1 MiB**） |
| `400` | 非 UTF-8 解码失败（`detail` 说明 encoding 错误） |
| `400` / `403` | 解析出的路径越出 KB 根目录（沿用 `safe_target_under_kb`） |

### 2.4 实现要点

1. 经 `_resolve_active_kb` 校验知识库。
2. `knowledge.get_source(source_id)`；不存在 → 404。
3. 用现有 `build_source_response` / URI 解析得到 `relative_path`，再 `safe_target_under_kb` 定位文件。
4. `stat().st_size` 超限 → 413，不读入内存。
5. `path.read_text(encoding="utf-8")`；`UnicodeDecodeError` → 400。
6. 配置项（可选，有默认即可）：`AKOS_SOURCE_CONTENT_MAX_BYTES`，默认 `1048576`。

---

## 3. 前端交互

### 3.1 入口（`SourceFileBrowser`）

每个文件行：

- 文件名变为可聚焦按钮/链接样式，点击打开预览。
- 操作区增加 **「查看」**，与「查看萃取 / 移动 / 删除」并列；点击同样打开预览。
- 两者打开同一弹层状态，避免双开。

### 3.2 弹层

- 居中 Modal + 半透明遮罩。
- 标题：`relative_path`（或 `title`），副信息可显示 `size_bytes`。
- 正文：可滚动 `<pre class="source-content-pre">`，等宽、保留空白与换行。
- 关闭：右上角关闭按钮、点击遮罩、`Escape`。
- 加载中：弹层内简短 status 文案；失败：弹层内或沿用页面 `ErrorBanner` 均可，优先弹层内错误，避免关层后丢失上下文。

### 3.3 API 客户端

`web/src/api/sources.ts` 增加 `fetchSourceContent(kbId, sourceId)`，映射到上述端点。

---

## 4. 测试

- 后端：存在文件返回 content；缺失 404；超限 413；非法编码 400。
- 前端：点击文件名与「查看」均打开弹层并展示 mock 正文；关闭后状态清空。

---

## 5. 验收标准

1. 在文档树对任意已入库 `.md` / `.txt`，点文件名或「查看」均可看到原文。
2. 弹层为居中层，正文等宽纯文本，无渲染差异（标题符号等原样可见）。
3. 超过 1 MiB 的文件给出明确失败，不撑爆浏览器。
4. 不提供编辑保存；移动/删除/萃取行为不变。

---

## 6. 非目标回顾

跨库预览、版本 diff、语法高亮、流式大文件均为后续可选，本规格不做。
