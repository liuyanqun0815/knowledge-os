# AKOS 管理台前端设计规格 — Admin Web（功能主导航）

**日期**: 2026-09-08  
**状态**: 已确认（brainstorming 决策）  
**依赖**:
- 二期总规格 `docs/superpowers/specs/2026-09-08-akos-phase2-design.md`（admin_api、knowledge_base_id、`POST /ask`）
- Phase 2.1 plan `docs/superpowers/plans/2026-09-08-akos-phase2-1-knowledge-base.md`
**原则**: 前端只消费 HTTP JSON；不嵌入领域逻辑；一切库相关操作显式带 `knowledge_base_id`

---

## 1. 动机与范围

二期规格明确 **admin_api 返回 JSON**，并将「完整 Web 管理台 SPA」标为 2.4 不做 / 三期可选。运营验收「建库 → 上传 → 问答」若仅靠 Swagger/CLI，成本高且难以展示证据与 Agent 轨迹。

本规格补齐 **运营管理台前端** 的信息架构、页面交互与技术边界，并与 Phase 2.1 **并行交付**（API 就绪一块、UI 解锁一块）。

### 1.1 产品形态

| 决策 | 选择 |
|------|------|
| 形态 | 运营后台 SPA + **简易问答页**（非对外 C 端聊天产品） |
| 栈 | React + Vite + TypeScript，独立目录 `web/` |
| 排期 | Phase 2.1 起并行；F0–F3 为 2.1 前端验收 |
| 鉴权 | 无登录；可选共享密钥 Header `X-Admin-Token`（`ADMIN_API_TOKEN`） |
| 导航 | **方案 2：功能主导航** + 顶栏全局「当前库」选择器 |
| 2.1 成功标准 | 建库 → 上传 → 编译状态 → 选库提问 → 答案 + 证据 + **Agent 轨迹时间线** |

### 1.2 包含

- 知识库列表 / 创建 / 详情编辑 / 归档
- 文档上传与编译状态
- 问答：答案、证据列表、Agent 轨迹
- 顶栏功能导航 + 当前库上下文
- 后期页占位：Claim 浏览、quarantine 审批（随 2.2+ API 解锁）

### 1.3 不包含

- 登录 / SSO / 多用户 RBAC
- 对外品牌落地页、全民 Wiki 编辑
- 图谱可视化大屏、OMS 写操作
- 浏览器内执行 compile / LangGraph

---

## 2. 信息架构与壳层

### 2.1 顶栏主导航

```text
┌─────────────────────────────────────────────────────────────┐
│ AKOS  │  知识库  │  文档  │  问答  │  （后期：Claim | 隔离）   │
│       │                              当前库：[下拉选择 ▾]     │
└─────────────────────────────────────────────────────────────┘
```

- 一级按 **功能** 分栏（非按库分栏）
- **全局「当前库」** 固定在顶栏右侧；文档 / 问答 / Claim / 隔离均读此上下文
- 未选库时：依赖库的页面展示空态「请先选择知识库」，并链接到知识库页
- 当前库同步：URL query `?kb=`（优先）+ `localStorage` 记忆
- 未就绪功能：顶栏可见但标记「即将推出」，点击说明依赖阶段，不假装可用

### 2.2 路由

```text
/                    → 重定向 /knowledge-bases
/knowledge-bases     → 知识库列表 + 创建入口
/knowledge-bases/new → 创建知识库
/knowledge-bases/:id → 库详情 / 编辑 / 归档（不依赖顶栏当前库）

/sources             → 文档列表 / 上传（依赖当前库）
/ask                 → 问答 + 证据 + Agent 轨迹（依赖当前库）

/claims              → Claim 浏览（2.2+，依赖当前库）
/quarantine          → 隔离审批（2.2+，依赖当前库）
```

### 2.3 壳层布局

```text
┌──────────────────────────────────────────────┐
│ Logo │ 知识库 │ 文档 │ 问答 │ … │ 当前库 ▾ │
├──────────────────────────────────────────────┤
│                                              │
│              当前功能页内容区                   │
│                                              │
└──────────────────────────────────────────────┘
```

- 无左侧库列表；库切换 **只在顶栏一处**，避免双源
- 顶栏变更当前库时：文档 / 问答立即按新库清空或重新拉取，禁止串库展示

### 2.4 与 API 对应

| 前端 | 后端 |
|------|------|
| 库 CRUD / 归档 | `/admin/knowledge-bases*` |
| 上传与文档列表 | `/admin/knowledge-bases/{id}/sources*` |
| 问答 | `POST /ask`（body 含 `knowledge_base_id`） |
| 轨迹 | 应答内嵌 `trace`，或 `GET /admin/knowledge-bases/{id}/traces/{request_id}` |
| 鉴权 | 可选请求头 `X-Admin-Token` |

---

## 3. 页面交互

### 3.1 知识库列表 `/knowledge-bases`

- 展示：名称、`domain_type`、状态、更新时间；行点击进入详情
- 「新建知识库」→ `/knowledge-bases/new`
- 最小筛选：状态 active/archived；按名称搜索
- 「设为当前」：更新顶栏选择器，并同步 `?kb=` / `localStorage`

### 3.2 创建 `/knowledge-bases/new`

- 字段：`name`（必填）、`domain_type`（下拉，已注册领域）、`description`（可选）
- 成功：`POST /admin/knowledge-bases` → 跳转详情，并 **自动设为当前库**
- 失败：字段校验错误或页顶 API 错误横幅

### 3.3 详情 `/knowledge-bases/:id`

- 只读元数据 + 可编辑 name/description
- **归档**：二次确认；归档后前端禁用上传/提问（与 API 拒绝一致并提示）
- 快捷入口：「管理文档」「去问答」——跳转对应功能页并带上该 `kb`

### 3.4 文档 `/sources`

- 未选库 → 空态 + 去知识库
- 上传：拖拽/选择文件（类型与后端约定一致）；走既有 upload 并触发 compile
- 列表：文件名、上传时间、编译状态 `pending` | `running` | `succeeded` | `failed`
- 刷新：短轮询（约 2s），终态后停止；支持手动刷新
- 失败：展示错误摘要，不伪装成功

### 3.5 问答 `/ask`（含 Agent 轨迹）

```text
┌─ 提问区 ─────────────────────────────┐
│ 当前库提示 | 问题输入 | 可选 as_of   │
│ [提问]                               │
├─ 答案 + 证据 ────────────────────────┤
│ 答案正文                             │
│ 证据列表：claim / 原文片段 / 可展开  │
├─ Agent 轨迹 ─────────────────────────┤
│ 时间线：节点名 · 状态 · 耗时 · 摘要  │
│ 节点可展开看 detail                  │
└──────────────────────────────────────┘
```

- 请求：`POST /ask`，含 `knowledge_base_id`、`question`，可选 `session_id` / `as_of`
- 证据：有则列表；无则明确「无证据」
- 轨迹：优先应答内 `trace` / `agent_steps`；否则用 `request_id` 拉 traces API；皆无则「轨迹暂不可用」
- 加载：按钮禁用 + 轨迹区 skeleton；错误条保留上次成功结果（若有）
- 归档库：禁用提问并提示

### 3.6 后期占位

- `/claims`、`/quarantine`：顶栏「即将推出」；交互与二期 admin 路由对齐（筛选、history、approve），本规格不展开实现细节

### 3.7 全局约定

- Token：`VITE_ADMIN_API_TOKEN` 或本地设置写入 `localStorage`（不进 git）
- 每页具备空态 / 加载 / 错误三态
- 文案中文；状态用语义色（成功 / 失败 / 进行中）

---

## 4. 技术结构

### 4.1 目录

```text
knowledge-os/
├── web/
│   ├── package.json
│   ├── vite.config.ts          # 代理 /admin、/ask → FastAPI
│   ├── src/
│   │   ├── app/                # 路由、Layout、KbContext
│   │   ├── pages/
│   │   ├── components/         # KbSwitcher、TraceTimeline、EvidenceList…
│   │   ├── api/                # fetch、类型、Token Header
│   │   └── styles/
│   └── README.md
├── app/
└── admin_api/
```

### 4.2 开发与部署

| 场景 | 做法 |
|------|------|
| 本地 | Vite 代理 `/admin`、`/ask` → `http://127.0.0.1:8000` |
| 生产 | 构建 `web/dist`；FastAPI 或 nginx 托管，或独立静态站 + CORS |
| Token | Header `X-Admin-Token` |

示例（Vite 代理）：

```ts
// web/vite.config.ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/admin": "http://127.0.0.1:8000",
      "/ask": "http://127.0.0.1:8000",
    },
  },
});
```

示例（当前库 + Token 请求）：

```ts
// web/src/api/client.ts
export async function ask(
  knowledgeBaseId: string,
  question: string,
  token?: string,
): Promise<AskResponse> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (token) {
    headers["X-Admin-Token"] = token;
  }
  const res = await fetch("/ask", {
    method: "POST",
    headers,
    body: JSON.stringify({
      knowledge_base_id: knowledgeBaseId,
      question,
    }),
  });
  if (!res.ok) {
    throw new Error(await res.text());
  }
  return res.json();
}
```

### 4.3 前端状态

- 当前库：React Context + URL `?kb=`（优先）+ `localStorage`
- 服务端数据：页面级拉取即可；2.1 不强制 React Query
- 问答结果：页内 state；切库清空

### 4.4 轨迹契约（后端需对齐）

应答增加可选字段（推荐）：

```ts
type AgentTraceStep = {
  node: string;
  status: "ok" | "error" | "skipped";
  duration_ms?: number;
  summary?: string;
  detail?: unknown;
};

type AskResponse = {
  answer: string;
  evidence?: EvidenceItem[];
  request_id?: string;
  trace?: AgentTraceStep[];
};
```

前端兼容路径：

1. 使用 `trace`（或同义 `agent_steps`）
2. 否则 `GET .../traces/{request_id}`
3. 否则降级文案「轨迹暂不可用」

### 4.5 UI 基线

- 管理工具风：清晰字号与间距；非营销落地页、非重型 Pro 模板
- 可用轻量头（如 Radix + CSS Modules / 自写 CSS）
- 避免默认「紫渐变仪表盘」审美；保持克制、可读

---

## 5. 分期交付与验收

| 切片 | 内容 | 依赖 |
|------|------|------|
| F0 | 壳层 + 顶栏 + KbSwitcher + Token 设置 | 无 |
| F1 | 知识库列表 / 创建 / 详情归档 | admin KB API |
| F2 | 文档上传 + 状态轮询 | sources upload/list |
| F3 | 问答 + 证据 + 轨迹时间线 | `/ask` + trace 或 debug API |
| F4 | Claim / quarantine | 2.2+ admin 路由 |

**Phase 2.1 前端验收 = F0–F3**，对应成功标准：

> 后台 UI 创建知识库并上传文档；编译状态可见；选库提问得到答案与证据；Agent 轨迹时间线可见（或明确降级提示且问答本身成功）。

---

## 6. 与二期规格的关系

| 二期原文 | 本规格 |
|----------|--------|
| 2.4「不做完整 Web 管理台 SPA」 | 本规格将 SPA 提前为 **2.1 并行** 的独立交付物；建议在二期总规格中改为「管理台 Web 见 admin-web 规格」 |
| 「Web UI 三期可选」 | 对本管理台不再适用；全民 Wiki 等仍属更远期 |
| admin_api JSON | 不变；Web 为消费者 |

---

## 7. 决策记录

| # | 决策 | 选择 |
|---|------|------|
| 1 | 产品深度 | 管理台 + 简易问答（含轨迹） |
| 2 | 技术栈 | React + Vite + TypeScript，`web/` |
| 3 | 排期 | Phase 2.1 并行，F0–F3 验收 |
| 4 | 鉴权 | 无登录 + 可选 `X-Admin-Token` |
| 5 | 导航 | 功能主导航 + 顶栏当前库 |
| 6 | 知识库管理 | 必须有（列表/创建/详情/归档） |
