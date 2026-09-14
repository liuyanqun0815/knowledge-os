# AKOS 问答页对话式 UI + 节点耗时 — 设计规格

**日期**: 2026-09-14  
**状态**: 已确认  
**依赖**:
- 现有：`web/src/pages/AskPage.tsx`、`web/src/api/ask.ts`、`orchestrator/nodes.py`、`orchestrator/trace_utils.py`、`orchestrator/graphs/ask_graph.py`
- API：`POST /ask?include_trace=true`（`session_id` 可选）

**原则**:
1. **样式对齐对话执行框**：助手气泡内「执行结果 · N 步」+ 回答 + 总耗时  
2. **会话暂不落库**：前端内存多轮；刷新 / 换库清空；Ask 本阶段不 `remember`  
3. **真实节点耗时**：后端各 ask node 写入 `trace[].duration_ms`  
4. **步骤默认折叠**：整卡与逐步均默认收起，按需展开看 summary / detail（含证据）

---

## 1. 已确认决策

| # | 决策 | 选择 |
|---|------|------|
| D1 | 交互形态 | **A：完整对话流**（多轮气泡，内存） |
| D2 | 证据 / 摘要 | **B 变体**：轻量摘要保留置信度 + 检索模式；**不要核验状态**；证据进步骤展开 |
| D3 | 会话 | **C**：前端生成 `session_id` 并传给 `/ask`；本阶段不持久化聊天；Ask **跳过 remember** |
| D4 | 步骤折叠 | 默认全部折叠 |
| D5 | 实现路径 | 方案 1：前端聊天壳 + 后端补节点耗时 |

---

## 2. 动机

当前问答页为表单 + 结果卡片（回答 meta / 证据 / Agent 轨迹分栏），与目标「执行步骤框」体验差距大；轨迹虽支持 `duration_ms`，但各 node 基本未填充，仅有整次 Ask 总耗时。

目标：管理端问答更接近对话式执行结果展示，并暴露可观测的分步耗时；会话记录延后，先内存可用。

---

## 3. 交互与信息架构

### 3.1 布局

- 上方：消息流（可滚动）
- 底部：固定输入区（问题 textarea、可选「截至时间」、发送）
- 无 KB：沿用 EmptyState

### 3.2 会话生命周期

- 进入页或当前 `kbId` 变化时：`sessionId = crypto.randomUUID()`，清空 `messages`
- 刷新页面：全部丢失（不写 localStorage）
- 每次提问：`askQuestion({ ..., sessionId, includeTrace: true })`
- Ask 图中 `remember_node`：本阶段不写 episode（空操作 / early return），避免 UI「内存会话」与 PG `memory_episodes` 不一致

### 3.3 气泡内容

**用户**：右侧文本气泡 + 时间戳  

**助手**：
1. **执行结果 · N 步**（`AskExecutionCard`）
   - 整卡可折叠；打开时列出步骤行
   - 每步：节点中文名、状态勾/失败、**节点耗时**；点击展开 summary + `TraceStepDetail`（证据等）
   - **各步骤默认折叠**
2. 最终回答正文 `result.text`
3. 轻量摘要行：置信度、检索模式（**不展示核验状态**）
4. 底栏灰字：本地时间 + 总耗时 `duration_ms`

轨迹为空：仍展示回答与总耗时；步骤区提示「轨迹暂不可用」。

---

## 4. 组件与数据

### 4.1 前端组件

| 组件 | 职责 |
|------|------|
| `AskPage` | 消息列表、sessionId、提交、KB 重置 |
| `AskMessageBubble` | 用户/助手气泡壳 |
| `AskExecutionCard` | 执行结果 N 步；默认折叠；行内耗时 |
| 复用 `TraceStepDetail` | 步骤展开详情 |
| 现有 `TraceTimeline` | 保留给 debug；问答页不再主用 |

### 4.2 内存消息模型

```ts
type AskChatMessage = {
  id: string;
  role: "user" | "assistant";
  text: string;           // user 原文；assistant 可为占位或最终回答
  createdAt: string;      // ISO
  status?: "pending" | "ok" | "error";
  result?: AskResponse;   // 含 trace、duration_ms、confidence、retrieval_mode、evidence…
  error?: string;
};
```

### 4.3 后端节点耗时

- 在 ask 相关 node（`recall`、`parse_time`、`normalize`、`route_mode`、`retrieve`、`verify`、`explain`、`synthesize`、`answer`；以及跳过的 `remember` 若仍跑则 duration≈0 或不记）入口/出口用 `time.perf_counter()`，经 `trace_step(..., duration_ms=…)` 写入。
- `normalize_agent_trace` 已支持 `duration_ms`（int）。
- `LangGraphOrchestrator.ask` 继续计算整次 `answer.duration_ms`。

### 4.4 remember 行为（本阶段）

- `remember_node`：不调用 `deps.memory.remember_episode`（可保留 trace 一步 `skipped` + 可选 duration，或直接 `{}`）。
- `recall` 可继续调用；无历史 episode 时结果为空，无害。
- 后续若要落库会话，另开规格，再打开 remember。

---

## 5. 加载 / 错误 / 非目标

### 5.1 加载

- 提交后立即追加 user 气泡 + assistant `pending` 占位
- 发送中禁用输入；用序号忽略过期响应

### 5.2 错误

- 失败时 assistant 气泡 `status=error` + 文案（如「提问失败，请稍后重试。」）
- 不强制顶部 ErrorBanner（可选保留）

### 5.3 非目标

- 会话列表、聊天持久化、流式 token、改检索/合成算法、E2E 浏览器自动化

---

## 6. 测试范围

- **前端**：多轮内存追加；换 KB 清空并换 `sessionId`；步骤默认折叠；摘要无核验文案；请求带 `session_id`
- **后端**：各 node `duration_ms` 为非负 int；Ask 路径不写 memory episode
- 更新现有 `AskPage.test.tsx` / 相关 orchestrator / ask 测试

---

## 7. 验收标准

1. 问答页呈现对话流，视觉接近「执行结果 N 步」样式框  
2. 步骤默认折叠；展开可见详情与证据相关 detail  
3. 每步与整次均有耗时展示（后端真实填充节点耗时）  
4. 刷新或换库后对话消失；Ask 不持久化 episode  
5. 回答区不展示核验状态；可展示置信度与检索模式  
