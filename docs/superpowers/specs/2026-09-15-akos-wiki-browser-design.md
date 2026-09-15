# AKOS Wiki 浏览页 — 设计规格

**日期**: 2026-09-15  
**状态**: 已确认  
**依赖**:
- 编译层 Wiki：`{data_root}/kb/{kb_id}/wiki/`（`wiki/paths.py`）
- 元数据：`wiki/meta.py`（`.meta/pages.json`）
- 管理台布局：`web/src/app/Layout.tsx`、`KbContext`、`TopNav`

**原则**:
1. **只读浏览**：一期不编辑 Wiki 文件  
2. **真实页互链**：仅 `[[folder/slug|标题]]` 且存在于 tree 时可跳转  
3. **全库关键字搜索**：标题 / 摘要 / 正文子串匹配 + 命中高亮  

---

## 1. 已确认决策

| # | 决策 | 选择 |
|---|------|------|
| D1 | 布局 | **A：左右分栏**（左目录/搜索结果，右 Markdown 正文） |
| D2 | 搜索 | **B：全库内容搜索** → 结果列表 → 打开页并高亮 |
| D3 | 实现路径 | **方案 1**：后端轻量 GET API + 前端 Markdown 渲染 |
| D4 | 数据源 | 仅编译层 `compile_wiki_root`，不用 export 路径 |
| D5 | 入口 | 顶栏新增「Wiki」，路由 `/wiki` |

---

## 2. 动机

当前 Wiki 已编译为可读目录树（`index.md` + hub 子页 + Obsidian 风格 wikilink），但管理台：

- 无浏览入口（仅知识库详情「导出 Wiki」）  
- 无 list/read/search GET API  
- 无 Markdown 渲染与 wikilink 跳转  

目标：像轻量 Obsidian 一样浏览当前知识库的编译 Wiki，并支持关键字检索与高亮。

---

## 3. 页面布局与交互

### 3.1 路由

```text
/wiki?kb={kbId}&page={pageId}&q={keyword}
```

- `kb`：与现有 `KbContext` 一致  
- `page`：Wiki `page_id`（如 `售后/七天无理由退货`），缺省为 `index` 或树中第一页  
- `q`：搜索关键字；有值时左侧优先展示搜索结果  

### 3.2 布局

```text
┌─────────────────────────────────────────────────────────┐
│ 搜索框 [关键字…]              命中 N 篇 · 清空           │
├──────────────┬──────────────────────────────────────────┤
│ 目录树       │  正文区                                   │
│ ▾ 售后       │  # 标题                                   │
│   · 七天…    │  Markdown 渲染                            │
│ ▾ 商品咨询   │  [[真实页]] 可点跳转                      │
│ （搜索时）   │  关键字 <mark>高亮</mark>                 │
│ 结果列表     │                                          │
└──────────────┴──────────────────────────────────────────┘
```

### 3.3 交互规则

1. **默认**：左侧 hub/页树；右侧打开 `index`（若存在）或第一篇 page。  
2. **点树节点**：更新 `?page=`，加载对应 Markdown。  
3. **点正文 wikilink**：  
   - 目标 `page_id` 存在于 tree → 跳转并更新 URL  
   - `source-` / `chunk-` / 假实体链接 → 不跳转（保留纯文本或弱样式）  
4. **搜索**：请求全库 search；左侧切到结果列表（标题 + snippet）；点结果打开页并对 `q` 高亮；可切回目录树。  
5. **空态**：未选 KB / wiki 根不存在 / 无页面 → `EmptyState` 明确提示。  

---

## 4. 后端 API

挂载于现有 `admin_api/routes_wiki.py`（`/admin` + admin token）。

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/knowledge-bases/{kb_id}/wiki/tree` | hub 分组目录 |
| `GET` | `/knowledge-bases/{kb_id}/wiki/pages/{page_id:path}` | 单页 markdown |
| `GET` | `/knowledge-bases/{kb_id}/wiki/search?q=&limit=` | 全库子串搜索 |

### 4.1 Tree

- 数据：`load_pages_meta(wiki_root)` + 可选解析 `index.md` 的 hub 描述（`> …`）  
- 跳过 `_index.md`（若仍有遗留）与 `.meta`  
- 响应：

```json
{
  "kb_id": "...",
  "wiki_root": "...",
  "hubs": [
    {
      "name": "售后",
      "description": "涵盖七天无理由退货、…",
      "pages": [
        {
          "page_id": "售后/七天无理由退货",
          "title": "七天无理由退货",
          "summary": "…"
        }
      ]
    }
  ]
}
```

### 4.2 Page

- `page_id`：`index` → `index.md`；否则 `{page_id}.md`  
- 必须 resolve 在 `compile_wiki_root` 内（防路径穿越）  
- 404：文件不存在  
- 响应：`page_id`, `title`, `path`, `markdown`

### 4.3 Search

- 匹配字段：`title`、`summary`、正文（utf-8）  
- 规则：不区分大小写子串；`q` 去空白后长度 ≥ 1  
- 每页最多 3 条 snippet（命中处 ±40 字）  
- 排序：标题命中 > 摘要命中 > 正文命中；同级按 title  
- `limit` 默认 50，上限 100  

```json
{
  "query": "退款",
  "total": 3,
  "hits": [
    {
      "page_id": "售后/退款到账时效",
      "title": "退款到账时效",
      "snippets": ["…退款总到账时间从商家确认…"]
    }
  ]
}
```

---

## 5. 前端实现要点

| 项 | 选择 |
|----|------|
| 路由 | `/wiki` → `WikiPage` |
| 导航 | `TopNav` 增加「Wiki」 |
| API | 扩展 `web/src/api/wiki.ts`：`fetchWikiTree` / `fetchWikiPage` / `searchWiki` |
| Markdown | `react-markdown` + `remark-gfm` |
| Wikilink | 自定义渲染：解析 `[[path\|label]]` / `[[path]]` |
| 高亮 | 有 `q` 时对文本节点包裹 `<mark>`；结果 snippet 同步高亮 |
| 样式 | 沿用现有 admin 视觉变量，左右分栏可用 CSS grid |

组件建议拆分（可按实现微调）：

- `WikiPage`：状态、URL sync、空态  
- `WikiSidebar`：树 / 搜索结果切换  
- `WikiMarkdown`：markdown + wikilink + highlight  
- `WikiSearchBar`：输入与清空  

---

## 6. 验收

1. 顶栏可进入 Wiki，左右分栏可读目录与正文  
2. 点真实 `[[售后/退换货流程|退换货流程]]` 能跳转并更新 URL  
3. 搜「退款」列出多页命中；点开后正文高亮关键字  
4. 假实体 / `source-` / `chunk-` 链接不误跳  
5. 未选 KB 或尚未编译 wiki 时有明确空态  
6. 路径穿越类 `page_id`（`../`）返回 400/404  

---

## 7. 非目标（一期）

- Wiki 在线编辑 / 保存  
- 向量语义搜索或复用 Ask 的 `WikiPageRetrieval` 打分  
- 导出路径（`{data_root}/{kb_id}/wiki`）浏览  
- 移动端专门布局  
- 将 Ask 回答改为 Markdown 渲染（可后续复用组件）  

---

## 8. 实施分期

| 阶段 | 范围 |
|------|------|
| **P0** | GET tree/page/search + schemas + 测试 |
| **P1** | `/wiki` 页：树 + 正文 + wikilink 跳转 |
| **P2** | 全库搜索结果列表 + 正文/snippet 高亮 |

---

## 9. 风险

| 风险 | 缓解 |
|------|------|
| 大库全文扫描慢 | 一期 KB 规模小；可后续加简单缓存或限制正文扫描大小 |
| wikilink 歧义（仅标题无路径） | 一期优先带路径的链接；仅标题时在同 hub / 全库唯一匹配时跳转，否则不跳 |
| Markdown XSS | `react-markdown` 默认不渲染 raw HTML；勿开 `rehype-raw` |
