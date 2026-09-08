# AKOS Admin Web（管理台前端）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 交付 React 管理台 `web/`：功能主导航 + 当前库选择器，完成知识库 CRUD、文档上传/状态、问答（答案+证据+Agent 轨迹），满足 Phase 2.1 前端验收 F0–F3。

**Architecture:** 独立 Vite SPA，经代理调用 FastAPI `/admin/*` 与 `POST /ask`；`KbContext` 用 URL `?kb=`（优先）+ `localStorage` 同步当前库；页面只做 HTTP 消费，不嵌入领域逻辑。轨迹优先读应答 `trace`，否则 `request_id` 拉 traces API，皆无则降级文案。

**Tech Stack:** React 18、Vite 5、TypeScript 5、React Router 6、Vitest + Testing Library、纯 CSS（无重型 UI 套件）

**Spec:** `docs/superpowers/specs/2026-09-08-akos-admin-web-design.md`

**Prerequisite:** Phase 2.1 admin KB/sources API（`docs/superpowers/plans/2026-09-08-akos-phase2-1-knowledge-base.md` Task 7）可用；本计划 Task 2 补齐 ask 的 `knowledge_base_id` 与可选 `trace`。

**Out of scope:** F4 Claim/quarantine 完整页（仅占位）、登录/SSO、生产 nginx 细调、图谱可视化

## Global Constraints

- 目录仅 `web/`（前端）+ 必要的 `app/` / `admin_api/` 契约对齐；禁止在前端写 compile/编排逻辑
- 一切库相关请求显式带 `knowledge_base_id`；禁止隐式租户 Header 切库
- 鉴权：无登录；可选 `X-Admin-Token`（与 `ADMIN_API_TOKEN` 对齐）
- 导航：功能主导航（知识库 | 文档 | 问答）；顶栏唯一「当前库」选择器
- Ask 响应兼容现有字段：`text`、`claim_ids`、`evidence`、`confidence`、`retrieval_mode`；扩展可选 `request_id`、`trace`
- 中文文案；空态/加载/错误三态；切库清空问答结果
- 每个 Task：相关测试 PASS + git commit
- black 仅约束本计划触及的 Python；前端用 Prettier 默认或项目已有格式即可

---

## File Structure

```text
knowledge-os/
├── web/
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── tsconfig.app.json
│   ├── index.html
│   ├── .env.example
│   ├── README.md
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── vite-env.d.ts
│       ├── styles/
│       │   └── global.css
│       ├── app/
│       │   ├── Layout.tsx
│       │   ├── KbContext.tsx
│       │   └── router.tsx
│       ├── api/
│       │   ├── types.ts
│       │   ├── http.ts
│       │   ├── knowledgeBases.ts
│       │   ├── sources.ts
│       │   └── ask.ts
│       ├── components/
│       │   ├── TopNav.tsx
│       │   ├── KbSwitcher.tsx
│       │   ├── EmptyState.tsx
│       │   ├── ErrorBanner.tsx
│       │   ├── EvidenceList.tsx
│       │   └── TraceTimeline.tsx
│       ├── pages/
│       │   ├── KnowledgeBaseListPage.tsx
│       │   ├── KnowledgeBaseNewPage.tsx
│       │   ├── KnowledgeBaseDetailPage.tsx
│       │   ├── SourcesPage.tsx
│       │   ├── AskPage.tsx
│       │   └── ComingSoonPage.tsx
│       └── test/
│           └── setup.ts
├── app/
│   └── routes.py                 # AskRequest + optional trace fields
├── admin_api/                    # 由 2.1 plan 创建；本计划只消费
│   └── (routes_knowledge_bases.py, routes_sources.py)
└── tests/
    └── test_ask_kb_and_trace.py  # 后端契约
```

---

### Task 1: 脚手架 `web/`（Vite + React + TS + Vitest）

**Files:**
- Create: `web/package.json`, `web/vite.config.ts`, `web/tsconfig.json`, `web/tsconfig.app.json`, `web/index.html`, `web/src/main.tsx`, `web/src/App.tsx`, `web/src/vite-env.d.ts`, `web/src/styles/global.css`, `web/src/test/setup.ts`, `web/.env.example`, `web/README.md`
- Modify: 根 `.gitignore`（若尚未忽略 `web/node_modules`、`web/dist`）

**Interfaces:**
- Consumes: 无
- Produces: 可运行的 Vite 开发服；`npm test` 跑通空套件

- [ ] **Step 1: 初始化 package.json 与 Vite 配置**

`web/package.json`:

```json
{
  "name": "akos-admin-web",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview",
    "test": "vitest run",
    "test:watch": "vitest"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-router-dom": "^6.28.0"
  },
  "devDependencies": {
    "@testing-library/jest-dom": "^6.6.3",
    "@testing-library/react": "^16.0.1",
    "@testing-library/user-event": "^14.5.2",
    "@types/react": "^18.3.12",
    "@types/react-dom": "^18.3.1",
    "@vitejs/plugin-react": "^4.3.3",
    "jsdom": "^25.0.1",
    "typescript": "~5.6.3",
    "vite": "^5.4.10",
    "vitest": "^2.1.4"
  }
}
```

`web/vite.config.ts`:

```ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/admin": "http://127.0.0.1:8000",
      "/ask": "http://127.0.0.1:8000",
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    css: true,
  },
});
```

`web/src/test/setup.ts`:

```ts
import "@testing-library/jest-dom/vitest";
```

`web/.env.example`:

```text
VITE_ADMIN_API_TOKEN=
```

`web/README.md` 写明：`npm install` → 后端起在 `:8000` → `npm run dev` → 打开 `http://127.0.0.1:5173`。

- [ ] **Step 2: 最小 App 与全局样式**

`web/src/App.tsx` 暂渲染 `<p>AKOS Admin</p>`；`global.css` 设基础字体、颜色变量（非紫渐变；中性灰 + 单一强调色如 `#0F766E`）。

- [ ] **Step 3: 安装依赖并跑通空测试**

在 `web/` 新增 `src/smoke.test.ts`:

```ts
import { describe, expect, it } from "vitest";

describe("smoke", () => {
  it("runs", () => {
    expect(1 + 1).toBe(2);
  });
});
```

Run:

```bash
cd web && npm install && npm test && npm run build
```

Expected: tests PASS；build 成功。

- [ ] **Step 4: Commit**

```bash
git add web .gitignore
git commit -m "chore: scaffold admin web with Vite React TypeScript"
```

---

### Task 2: 后端契约 — ask 带 kb_id + 可选 trace / Token 中间件

**Files:**
- Modify: `app/routes.py`
- Create: `app/admin_auth.py`（可选 Token 校验）
- Modify: `app/main.py`（挂载 middleware 或 dependency）
- Modify: `.env.example`（`ADMIN_API_TOKEN=`）
- Test: `tests/test_ask_kb_and_trace.py`

**Interfaces:**
- Consumes: `LangGraphOrchestrator.ask`（2.1 已改为或即将改为接受 `knowledge_base_id`）
- Produces:
  - `AskRequest(knowledge_base_id: str, question: str, session_id: str | None, as_of: datetime | None)`
  - `AskResponse` 保留 `text/claim_ids/evidence/confidence/retrieval_mode`；增可选 `request_id: str | None`、`trace: list[dict] | None`
  - 若环境变量 `ADMIN_API_TOKEN` 非空，则 `/admin/*` 与 `/ask` 要求 Header `X-Admin-Token` 匹配，否则 401

- [ ] **Step 1: 写失败测试**

```python
# tests/test_ask_kb_and_trace.py
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_ask_requires_knowledge_base_id():
    r = client.post("/ask", json={"question": "hello"})
    assert r.status_code == 422


def test_ask_response_may_include_trace_fields(monkeypatch):
    # 若 2.1 orchestrator 尚未就绪，用 dependency override 返回带 trace 的假 Answer
    ...
    r = client.post(
        "/ask",
        json={"knowledge_base_id": "kb-1", "question": "定制商品能否退货？"},
    )
    assert r.status_code == 200
    body = r.json()
    assert "text" in body
    assert "evidence" in body
    assert "request_id" in body  # may be null
    assert "trace" in body  # may be null or list
```

实现时：用 FastAPI `dependency_overrides` mock orchestrator，避免强依赖 PG。

- [ ] **Step 2: 跑测试确认失败**

```bash
pytest tests/test_ask_kb_and_trace.py -v
```

Expected: FAIL（缺字段或 422 行为不符）

- [ ] **Step 3: 最小实现**

更新 `AskRequest` / `AskResponse`；`ask` 调用 `orchestrator.ask(knowledge_base_id=..., question=..., session_id=...)`；若编排暂无 trace，返回 `request_id=None, trace=None` 仍通过契约测试。

`app/admin_auth.py`:

```python
import os

from fastapi import Header, HTTPException


def require_admin_token(x_admin_token: str | None = Header(default=None)) -> None:
    expected = os.getenv("ADMIN_API_TOKEN", "").strip()
    if not expected:
        return
    if x_admin_token != expected:
        raise HTTPException(status_code=401, detail="invalid admin token")
```

将 dependency 挂到 `/ask` 与 `/admin` router。

- [ ] **Step 4: 测试通过**

```bash
pytest tests/test_ask_kb_and_trace.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/routes.py app/admin_auth.py app/main.py .env.example tests/test_ask_kb_and_trace.py
git commit -m "feat: require knowledge_base_id on ask and optional admin token"
```

---

### Task 3: API 客户端层（types + http + kb/sources/ask）

**Files:**
- Create: `web/src/api/types.ts`, `web/src/api/http.ts`, `web/src/api/knowledgeBases.ts`, `web/src/api/sources.ts`, `web/src/api/ask.ts`
- Test: `web/src/api/http.test.ts`, `web/src/api/ask.test.ts`

**Interfaces:**
- Consumes: `fetch`；`localStorage` key `akos_admin_token`；`import.meta.env.VITE_ADMIN_API_TOKEN`
- Produces:
  - `apiFetch(path, init?)`
  - `listKnowledgeBases()`, `createKnowledgeBase(body)`, `getKnowledgeBase(id)`, `updateKnowledgeBase(id, body)`
  - `listSources(kbId)`, `uploadSource(kbId, file)`
  - `askQuestion({ knowledgeBaseId, question, sessionId?, asOf? })`

- [ ] **Step 1: 写失败测试（Token Header）**

```ts
// web/src/api/http.test.ts
import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiFetch, getAdminToken, setAdminToken } from "./http";

describe("apiFetch", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("{}", { status: 200 })));
  });

  it("attaches X-Admin-Token when token is set", async () => {
    setAdminToken("secret");
    await apiFetch("/admin/knowledge-bases");
    expect(fetch).toHaveBeenCalledWith(
      "/admin/knowledge-bases",
      expect.objectContaining({
        headers: expect.objectContaining({ "X-Admin-Token": "secret" }),
      }),
    );
  });
});
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd web && npm test -- src/api/http.test.ts
```

Expected: FAIL module not found / function not defined

- [ ] **Step 3: 实现 types + http + 资源 API**

`web/src/api/types.ts`（关键字段）：

```ts
export type KnowledgeBase = {
  id: string;
  name: string;
  domain_type: string;
  description: string;
  status: "active" | "archived";
  created_at: string;
  updated_at: string;
};

export type SourceItem = {
  id: string;
  filename: string;
  created_at: string;
  compile_status: "pending" | "running" | "succeeded" | "failed";
  error_summary?: string | null;
};

export type AgentTraceStep = {
  node: string;
  status: "ok" | "error" | "skipped";
  duration_ms?: number;
  summary?: string;
  detail?: unknown;
};

export type AskResponse = {
  text: string;
  claim_ids: string[];
  evidence: Record<string, unknown>[];
  confidence: number;
  retrieval_mode: string;
  request_id?: string | null;
  trace?: AgentTraceStep[] | null;
};
```

`http.ts`：`getAdminToken` 优先 `localStorage`，否则 `import.meta.env.VITE_ADMIN_API_TOKEN`；非 2xx throw `Error` 含 `status` 与 body 文本。

各资源模块用相对路径 `/admin/...`、`/ask`。

- [ ] **Step 4: ask 映射测试**

```ts
// web/src/api/ask.test.ts
it("posts knowledge_base_id and question", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          text: "ok",
          claim_ids: [],
          evidence: [],
          confidence: 0.5,
          retrieval_mode: "hybrid",
          request_id: null,
          trace: null,
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    ),
  );
  const { askQuestion } = await import("./ask");
  await askQuestion({ knowledgeBaseId: "kb-1", question: "q" });
  expect(fetch).toHaveBeenCalledWith(
    "/ask",
    expect.objectContaining({
      method: "POST",
      body: JSON.stringify({ knowledge_base_id: "kb-1", question: "q" }),
    }),
  );
});
```

- [ ] **Step 5: 全绿并 Commit**

```bash
cd web && npm test
git add web/src/api
git commit -m "feat: add admin web API client with optional token"
```

---

### Task 4: F0 — KbContext、Layout、顶栏、路由占位

**Files:**
- Create: `web/src/app/KbContext.tsx`, `web/src/app/Layout.tsx`, `web/src/app/router.tsx`, `web/src/components/TopNav.tsx`, `web/src/components/KbSwitcher.tsx`, `web/src/components/EmptyState.tsx`, `web/src/components/ErrorBanner.tsx`, `web/src/pages/ComingSoonPage.tsx`
- Modify: `web/src/App.tsx`, `web/src/main.tsx`
- Test: `web/src/app/KbContext.test.tsx`

**Interfaces:**
- Consumes: `listKnowledgeBases`（KbSwitcher 拉列表；测试可 mock）
- Produces:
  - `KbProvider` / `useKb()` → `{ kbId, setKbId, clearKb }`
  - 路由表见 spec §2.2；`/claims`、`/quarantine` → `ComingSoonPage`

- [ ] **Step 1: KbContext 测试（URL 优先于 localStorage）**

```tsx
// web/src/app/KbContext.test.tsx
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useSearchParams } from "react-router-dom";
import { KbProvider, useKb } from "./KbContext";

function Probe() {
  const { kbId } = useKb();
  return <span data-testid="kb">{kbId ?? "none"}</span>;
}

it("prefers ?kb= over localStorage", () => {
  localStorage.setItem("akos_current_kb", "from-storage");
  render(
    <MemoryRouter initialEntries={["/ask?kb=from-url"]}>
      <KbProvider>
        <Routes>
          <Route path="/ask" element={<Probe />} />
        </Routes>
      </KbProvider>
    </MemoryRouter>,
  );
  expect(screen.getByTestId("kb").textContent).toBe("from-url");
});
```

- [ ] **Step 2: 跑测失败 → 实现 KbContext**

同步规则：

1. 读 `searchParams.get("kb")`，有则用之并写 `localStorage`
2. 否则读 `localStorage.akos_current_kb`
3. `setKbId(id)`：写 storage，并用 `setSearchParams` 更新 `kb`

- [ ] **Step 3: Layout + TopNav + KbSwitcher**

- 顶栏链接：`/knowledge-bases`、`/sources`、`/ask`；Claim/隔离链到 `/claims`、`/quarantine` 并标注「即将推出」
- KbSwitcher：`<select>` 绑定 `kbId`；选项来自 `listKnowledgeBases()`（失败时 ErrorBanner）
- Token：顶栏旁「设置」展开简单 input，调用 `setAdminToken`

占位页：

```tsx
export function ComingSoonPage({ title }: { title: string }) {
  return <EmptyState title={title} description="该功能随 2.2+ API 解锁。" />;
}
```

- [ ] **Step 4: 路由接入 App**

```tsx
// router 关键路由；默认 Navigate to /knowledge-bases
```

- [ ] **Step 5: 测试 + Commit**

```bash
cd web && npm test
git add web/src
git commit -m "feat: add admin shell with kb context and top nav"
```

---

### Task 5: F1 — 知识库列表 / 创建 / 详情归档

**Files:**
- Create: `web/src/pages/KnowledgeBaseListPage.tsx`, `web/src/pages/KnowledgeBaseNewPage.tsx`, `web/src/pages/KnowledgeBaseDetailPage.tsx`
- Test: `web/src/pages/KnowledgeBaseListPage.test.tsx`

**Interfaces:**
- Consumes: `listKnowledgeBases`, `createKnowledgeBase`, `getKnowledgeBase`, `updateKnowledgeBase`, `useKb().setKbId`
- Produces: 可操作的三个页面

- [ ] **Step 1: 列表页测试（mock API）**

```tsx
vi.mock("../api/knowledgeBases", () => ({
  listKnowledgeBases: vi.fn().mockResolvedValue([
    {
      id: "kb-1",
      name: "电商客服",
      domain_type: "ecommerce_cs",
      description: "",
      status: "active",
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
    },
  ]),
}));

it("renders knowledge base names", async () => {
  renderWithProviders(<KnowledgeBaseListPage />);
  expect(await screen.findByText("电商客服")).toBeInTheDocument();
});
```

- [ ] **Step 2: 实现列表页**

表格列：名称、domain_type、状态、更新时间；「新建」按钮；行点击 → `/knowledge-bases/:id`；「设为当前」调用 `setKbId`。

- [ ] **Step 3: 创建页**

表单字段 `name`、`domain_type`（select：`ecommerce_cs` | `corporate_culture` | `loan_finance` | `generic`）、`description`；提交成功后 `setKbId(created.id)` 并 `navigate(/knowledge-bases/${id})`。

- [ ] **Step 4: 详情页**

加载 `getKnowledgeBase`；可 PATCH name/description；归档按钮二次 `window.confirm` 后 `updateKnowledgeBase(id, { status: "archived" })`；快捷链到 `/sources?kb=`、`/ask?kb=`。

- [ ] **Step 5: 测试 + Commit**

```bash
cd web && npm test
git add web/src/pages
git commit -m "feat: add knowledge base list create and detail pages"
```

---

### Task 6: F2 — 文档上传与编译状态轮询

**Files:**
- Create: `web/src/pages/SourcesPage.tsx`
- Test: `web/src/pages/SourcesPage.test.tsx`

**Interfaces:**
- Consumes: `useKb()`, `listSources`, `uploadSource`
- Produces: `/sources` 页

- [ ] **Step 1: 未选库空态测试**

```tsx
it("shows empty state when no kb selected", () => {
  renderWithProviders(<SourcesPage />, { kbId: null });
  expect(screen.getByText(/请先选择知识库/)).toBeInTheDocument();
});
```

- [ ] **Step 2: 实现上传 + 列表**

- `input[type=file]` + 拖拽（`onDrop` 取 `dataTransfer.files[0]`）
- 上传中禁用按钮；失败 ErrorBanner
- 列表展示 `compile_status`；若存在 `pending`/`running`，`useEffect` 每 2s `listSources`，无进行中则清 interval
- 归档库：若详情 status 为 archived，禁用上传（可选：调用 getKnowledgeBase 检查）

- [ ] **Step 3: 轮询测试（假时钟）**

```tsx
it("polls while compile_status is running", async () => {
  vi.useFakeTimers();
  const listSources = vi
    .fn()
    .mockResolvedValueOnce([{ id: "s1", filename: "a.md", created_at: "", compile_status: "running" }])
    .mockResolvedValueOnce([{ id: "s1", filename: "a.md", created_at: "", compile_status: "succeeded" }]);
  // mock module; advance 2000ms; expect listSources called >= 2
  vi.useRealTimers();
});
```

- [ ] **Step 4: Commit**

```bash
cd web && npm test
git add web/src/pages/SourcesPage.tsx web/src/pages/SourcesPage.test.tsx
git commit -m "feat: add sources upload page with compile status polling"
```

---

### Task 7: F3 — 问答页（证据 + 轨迹时间线）

**Files:**
- Create: `web/src/pages/AskPage.tsx`, `web/src/components/EvidenceList.tsx`, `web/src/components/TraceTimeline.tsx`
- Modify: `web/src/api/ask.ts`（若需 `fetchTrace(kbId, requestId)`）
- Test: `web/src/components/TraceTimeline.test.tsx`, `web/src/pages/AskPage.test.tsx`

**Interfaces:**
- Consumes: `askQuestion`, 可选 `GET /admin/knowledge-bases/{id}/traces/{request_id}`
- Produces: 完整 `/ask` 页

- [ ] **Step 1: TraceTimeline 单元测试**

```tsx
it("renders node names in order", () => {
  render(
    <TraceTimeline
      steps={[
        { node: "retrieve", status: "ok", summary: "hit 3" },
        { node: "answer", status: "ok", summary: "done" },
      ]}
    />,
  );
  expect(screen.getByText("retrieve")).toBeInTheDocument();
  expect(screen.getByText("answer")).toBeInTheDocument();
});

it("shows fallback when steps empty", () => {
  render(<TraceTimeline steps={[]} unavailableReason="轨迹暂不可用" />);
  expect(screen.getByText("轨迹暂不可用")).toBeInTheDocument();
});
```

- [ ] **Step 2: 实现 EvidenceList + TraceTimeline**

- Evidence：渲染 `evidence` 数组；项可展开 JSON/`span` 文本；空则「无证据」
- Trace：时间线列表；点击展开 `detail`

- [ ] **Step 3: AskPage 流程**

1. 无 kb → EmptyState  
2. 输入 question，可选 as_of（`<input type="datetime-local">` → ISO 字符串）  
3. 提交 → `askQuestion`；展示 `text`、`EvidenceList`  
4. 若 `trace` 非空 → TraceTimeline  
5. 否则若 `request_id` → 尝试 fetch traces；失败或 404 →「轨迹暂不可用」  
6. 切库（监听 `kbId`）→ 清空 `result` state  

- [ ] **Step 4: AskPage 测试**

```tsx
it("shows answer text after ask", async () => {
  vi.mocked(askQuestion).mockResolvedValue({
    text: "不可退货",
    claim_ids: ["c1"],
    evidence: [{ claim_id: "c1", span: "定制商品不适用七天无理由" }],
    confidence: 0.9,
    retrieval_mode: "hybrid",
    request_id: "r1",
    trace: [{ node: "retrieve", status: "ok", summary: "ok" }],
  });
  // render, type, click 提问, findByText 不可退货 + retrieve
});
```

- [ ] **Step 5: Commit**

```bash
cd web && npm test
git add web/src/pages/AskPage.tsx web/src/components/EvidenceList.tsx web/src/components/TraceTimeline.tsx web/src/api
git commit -m "feat: add ask page with evidence and agent trace timeline"
```

---

### Task 8: 联调验收与文档收尾

**Files:**
- Modify: `web/README.md`、根 `README.md`（加管理台一节）
- Modify: `docs/superpowers/plans/2026-09-08-akos-phase2-1-knowledge-base.md` — Out of scope 去掉「Web 管理台 UI」，改为指向本 plan

**Interfaces:**
- Consumes: 本地 PG + admin API + web dev server
- Produces: 手工验收清单勾选

- [ ] **Step 1: 手工 E2E（对真实后端）**

```bash
# 终端 A
uvicorn app.main:app --reload --port 8000
# 终端 B
cd web && npm run dev
```

验收清单：

1. 创建知识库（如 `corporate_culture`）并自动成为当前库  
2. 上传 `.md`，列表出现且状态进入 `succeeded`（或失败有摘要）  
3. `/ask` 提问，看到 `text` 与 `evidence`  
4. 有 `trace` 则见时间线；无则见「轨迹暂不可用」且问答仍成功  
5. 切换当前库后问答区清空；未选库时空态正确  
6. 设置错误 Token（若启用 `ADMIN_API_TOKEN`）→ 401 有错误条  

- [ ] **Step 2: 更新 README 链接与 2.1 plan 交叉引用**

- [ ] **Step 3: Commit**

```bash
git add README.md web/README.md docs/superpowers/plans/2026-09-08-akos-phase2-1-knowledge-base.md
git commit -m "docs: document admin web setup and link phase 2.1 plan"
```

---

## Spec Coverage Checklist

| Spec 项 | Task |
|---------|------|
| React+Vite+TS、`web/` | 1 |
| 代理 /admin、/ask | 1 |
| X-Admin-Token | 2, 3, 4 |
| 功能主导航 + 当前库 | 4 |
| 路由含 claims/quarantine 占位 | 4 |
| 知识库 CRUD/归档 | 5 |
| 文档上传+轮询 | 6 |
| 问答+证据+轨迹降级 | 7 |
| F0–F3 验收 | 8 |
| F4 完整实现 | 明确不做（占位已覆盖） |

## Self-Review Notes

- Ask 字段与现网一致使用 `text`（非 spec 草稿中的 `answer`），避免前后端命名漂移  
- `SourceItem.compile_status` 若后端字段名不同，在 Task 6 按实际 JSON 改 `types.ts` 一处映射，勿散落魔法字符串  
- traces GET 可能晚于 2.1；Task 7 降级路径保证验收不阻塞  

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-09-08-akos-admin-web.md`.

**Two execution options:**

1. **Subagent-Driven（推荐）** — 每 Task 新开子代理，任务间审查  
2. **Inline Execution** — 本会话按 executing-plans 连续执行并设检查点  

Which approach?
