# AKOS Admin Web

AKOS 管理台前端（React + Vite + TypeScript），实现 Phase 2.1 前端验收 F0–F3。

**Implementation plan:** [`docs/superpowers/plans/2026-09-08-akos-admin-web.md`](../docs/superpowers/plans/2026-09-08-akos-admin-web.md)

## 本地开发

### 前置条件

- Node.js 18+
- 后端 API 运行于 `http://127.0.0.1:8000`（见根目录 [README.md](../README.md)）
- 可选：PostgreSQL（`AKOS_USE_PG=true`）用于跨会话持久化；InMemory 模式亦可联调

### 启动步骤

**终端 A — 后端：**

```bash
# 项目根目录
uvicorn app.main:app --reload --port 8000
```

**终端 B — 前端：**

```bash
cd web
npm install
npm run dev
```

浏览器打开 [http://127.0.0.1:5173](http://127.0.0.1:5173)。

Vite 开发服将 `/admin` 与 `/ask` 代理到后端 `:8000`。

### 环境变量

复制 `.env.example` 为 `.env.local` 并按需填写：

- `VITE_ADMIN_API_TOKEN` — 可选，与后端 `ADMIN_API_TOKEN` 对齐的管理 API 令牌

后端 `.env` 中对应变量：

- `ADMIN_API_TOKEN` — 非空时，所有 `/admin/*` 请求需携带 `X-Admin-Token`

## 脚本

| 命令 | 说明 |
|------|------|
| `npm run dev` | 开发模式 |
| `npm run build` | 生产构建 |
| `npm run preview` | 预览构建产物 |
| `npm test` | 运行测试（单次） |
| `npm run test:watch` | 监听模式测试 |

## 手工 E2E 验收清单

对**真实后端**逐项勾选（需同时启动后端与 `npm run dev`）：

- [ ] **创建知识库** — 创建如 `corporate_culture` 的库，并自动成为当前库
- [ ] **上传文档** — 上传 `.md` 文件，列表出现且状态进入 `succeeded`（失败时显示摘要）
- [ ] **问答** — 在 `/ask` 提问，看到 `text` 与 `evidence`
- [ ] **Agent 轨迹** — 有 `trace` 时见时间线；无则见「轨迹暂不可用」且问答仍成功
- [ ] **切换当前库** — 切换后问答区清空；未选库时空态正确
- [ ] **鉴权错误** — 设置错误 Token（启用 `ADMIN_API_TOKEN` 时）→ 401 有错误条

## 功能范围

| 范围 | 说明 |
|------|------|
| F0–F3 | 知识库 CRUD、文档上传/状态轮询、问答+证据+轨迹降级 |
| F4 | Claim/quarantine 仅占位页，完整实现见 admin-web plan Out of scope |
