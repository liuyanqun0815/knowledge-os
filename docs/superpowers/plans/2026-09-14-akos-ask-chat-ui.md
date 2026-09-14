# Ask Chat UI + Node Duration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the admin Ask page as an in-memory chat with collapsible per-node execution steps and real `duration_ms` on each orchestrator node, without persisting chat episodes.

**Architecture:** Backend ask nodes wrap work with `time.perf_counter()` and emit `trace_step(..., duration_ms=…)`; `remember_node` becomes a no-op (skipped). Frontend `AskPage` keeps `sessionId` + `messages[]` in React state, renders chat bubbles, and embeds `AskExecutionCard` (steps default collapsed) with confidence/mode summary—no verification badge.

**Tech Stack:** Python/LangGraph (`orchestrator/nodes.py`), FastAPI `/ask`, React + Vitest (`web/src/pages/AskPage.tsx`), existing `TraceStepDetail`.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-09-14-akos-ask-chat-ui-design.md` (confirmed)
- Steps **default collapsed**; no verification status in assistant summary
- In-memory only: no localStorage chat; Ask **must not** call `remember_episode`
- Frontend still sends `session_id` (UUID) on each ask
- black `max_line_length=120`; no `from module import *`; TDD; commit per task
- Dirty tree: stage **only** task files

## File map

| File | Responsibility |
|------|----------------|
| `orchestrator/nodes.py` | timed `trace_step`; skip remember |
| `orchestrator/trace_utils.py` | unchanged API (`duration_ms` already supported) |
| `tests/test_ask_node_duration.py` | assert per-node `duration_ms` + no remember |
| `web/src/components/AskExecutionCard.tsx` | 「执行结果 · N 步」 |
| `web/src/components/AskMessageBubble.tsx` | user/assistant bubbles |
| `web/src/pages/AskPage.tsx` | chat shell + session memory |
| `web/src/styles/global.css` | chat / execution card styles |
| `web/src/pages/AskPage.test.tsx` | chat + sessionId + no 核验 |
| `web/src/components/AskExecutionCard.test.tsx` | default collapsed |

---

### Task 1: Skip remember on Ask path

**Files:**
- Modify: `orchestrator/nodes.py` (`remember_node`)
- Test: `tests/test_ask_node_duration.py` (create; this task only remember cases)
- Modify if needed: any test that asserts `remember` wrote episodes for default ask

**Interfaces:**
- Produces: `remember_node` returns skipped trace, never calls `deps.memory.remember*` / `memory_agent.remember`

- [ ] **Step 1: Write failing test**

```python
# tests/test_ask_node_duration.py
from unittest.mock import MagicMock

from orchestrator.nodes import remember_node


def test_remember_node_skips_persistence():
    memory = MagicMock()
    deps = MagicMock()
    deps.memory = memory
    state = {
        "question": "有什么活动？",
        "session_id": "sess-1",
        "answer": MagicMock(text="满减活动"),
        "trace": [],
    }
    out = remember_node(state, deps)
    memory.remember_episode.assert_not_called()
    # if project uses memory_agent.remember via deps, also:
    assert "remember" not in str(memory.mock_calls).lower() or memory.method_calls == []
    steps = out.get("trace") or []
    assert len(steps) == 1
    assert steps[0]["node"] == "remember"
    assert steps[0]["status"] == "skipped"
```

Adjust assertion to match how `memory_agent.remember` is invoked (patch `orchestrator.nodes.memory_agent.remember` if that is the call site).

- [ ] **Step 2: Run test — expect FAIL**

Run: `pytest tests/test_ask_node_duration.py::test_remember_node_skips_persistence -v`  
Expected: FAIL (still calls remember)

- [ ] **Step 3: Implement skip**

```python
def remember_node(state: AskState, deps: Any) -> dict:
    # Phase: in-memory chat UI — do not persist episodes
    return {
        "trace": [
            trace_step(
                "remember",
                status="skipped",
                summary="本阶段不写入会话记忆",
                duration_ms=0,
            )
        ]
    }
```

- [ ] **Step 4: Run test — expect PASS**

Run: `pytest tests/test_ask_node_duration.py::test_remember_node_skips_persistence -v`

- [ ] **Step 5: Fix any broken orchestrator tests that required remember side effects; re-run those files**

- [ ] **Step 6: Commit**

```bash
git add orchestrator/nodes.py tests/test_ask_node_duration.py
git commit -m "feat: skip ask remember persistence for in-memory chat"
```

---

### Task 2: Per-node `duration_ms` on ask graph

**Files:**
- Modify: `orchestrator/nodes.py` — ask nodes: `recall_node`, `parse_time_node`, `normalize_node`, `route_mode_node`, `retrieve_node`, `verify_node`, `explain_node`, `synthesize_node`, `answer_node`
- Test: `tests/test_ask_node_duration.py` (extend)
- Optional helper in same file:

```python
def _node_duration_ms(started: float) -> int:
    return max(0, int((time.perf_counter() - started) * 1000))
```

**Interfaces:**
- Consumes: `trace_step` from `orchestrator.trace_utils`
- Produces: every ask node that contributes work emits at least one `trace` entry with `duration_ms: int >= 0`
- Nodes that previously returned `{}` without trace (`recall`, `parse_time`, `normalize`) must emit a timed step

- [ ] **Step 1: Failing integration-style test on real graph or node wrappers**

```python
def test_ask_trace_steps_include_non_negative_duration_ms(tmp_path, monkeypatch):
    # Build orchestrator the same way as tests/test_orchestrator.py (or invoke nodes with mocks)
    # Call ask(..., include_trace=True) with a fixed question
    # For each step in result.trace: assert isinstance(step["duration_ms"], int) and step["duration_ms"] >= 0
    # Assert nodes present include at least: route_mode, retrieve, verify, answer, remember
    ...
```

Prefer reusing existing orchestrator fixture from `tests/test_orchestrator.py` / `conftest.py` rather than inventing a new bootstrap.

- [ ] **Step 2: Run — expect FAIL** (many steps missing `duration_ms`)

- [ ] **Step 3: Instrument nodes**

Pattern for nodes that already return `trace`:

```python
def route_mode_node(state: AskState, deps: Any) -> dict:
    started = time.perf_counter()
    # ... existing logic ...
    return {
        "retrieval_mode": mode,
        "procedure": procedure,
        "trace": [
            trace_step(
                "route_mode",
                summary=...,
                detail=...,
                duration_ms=_node_duration_ms(started),
            )
        ],
    }
```

Pattern for nodes that returned `{}`:

```python
def recall_node(state: AskState, deps: Any) -> dict:
    started = time.perf_counter()
    memory_agent.recall(deps.memory, state["question"], state.get("session_id"))
    return {
        "trace": [
            trace_step(
                "recall",
                summary="会话回忆",
                duration_ms=_node_duration_ms(started),
            )
        ],
    }
```

Apply the same to `parse_time_node`, `normalize_node`, and all existing `trace_step(...)` call sites in retrieve/verify/explain/synthesize/answer.

Ensure `import time` at module top if missing.

- [ ] **Step 4: PASS** `pytest tests/test_ask_node_duration.py -v` plus `pytest tests/test_orchestrator.py tests/test_ask_trace.py -v` (or whichever ask trace tests exist)

- [ ] **Step 5: Commit**

```bash
git add orchestrator/nodes.py tests/test_ask_node_duration.py
git commit -m "feat: record duration_ms on ask graph nodes"
```

---

### Task 3: `AskExecutionCard` (default collapsed)

**Files:**
- Create: `web/src/components/AskExecutionCard.tsx`
- Create: `web/src/components/AskExecutionCard.test.tsx`
- Modify: `web/src/styles/global.css` (execution-card section only)

**Interfaces:**
- Consumes: `AgentTraceStep` from `../api/types`; `TraceStepDetail`
- Produces:

```tsx
export type AskExecutionCardProps = {
  steps: AgentTraceStep[];
  unavailableReason?: string;
};

export function AskExecutionCard({ steps, unavailableReason = "轨迹暂不可用" }: AskExecutionCardProps): JSX.Element;
```

- Default: **card body collapsed** OR if card open, **each step collapsed** (spec: 各步骤默认折叠). Recommended UX matching screenshot 2: card header visible (`执行结果 共 N 步`); step list visible when card expanded; **individual steps start collapsed**. Implement: `cardOpen` default `true` (list visible like screenshot) OR `false`—**spec says 默认折叠 for steps**; set `cardOpen` default `true`, `expandedStepIndexes` default empty `Set`. If product prefers whole card closed first, set `cardOpen` default `false`—**use `cardOpen=true`, steps collapsed** so users see step rows with chevrons without detail (closest to screenshot 2).

NODE_LABELS: copy from `TraceTimeline.tsx`.

- [ ] **Step 1: Failing component test**

```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AskExecutionCard } from "./AskExecutionCard";

it("renders step rows collapsed by default and shows duration", async () => {
  const user = userEvent.setup();
  render(
    <AskExecutionCard
      steps={[
        {
          node: "retrieve",
          status: "ok",
          summary: "命中 3 条",
          duration_ms: 1200,
          detail: { hit_count: 3 },
        },
      ]}
    />,
  );
  expect(screen.getByText(/执行结果/)).toBeInTheDocument();
  expect(screen.getByText(/混合检索|retrieve/)).toBeInTheDocument();
  expect(screen.getByText(/1\.20 秒|1200/)).toBeInTheDocument();
  expect(screen.queryByText("命中 3 条")).not.toBeInTheDocument(); // collapsed
  await user.click(screen.getByRole("button", { name: /混合检索|retrieve/ }));
  expect(screen.getByText("命中 3 条")).toBeInTheDocument();
});
```

- [ ] **Step 2: Run FAIL** — `cd web && npm test -- src/components/AskExecutionCard.test.tsx`

- [ ] **Step 3: Implement component + CSS**

Minimal structure:

```tsx
export function AskExecutionCard({ steps, unavailableReason = "轨迹暂不可用" }: AskExecutionCardProps) {
  const [cardOpen, setCardOpen] = useState(true);
  const [expanded, setExpanded] = useState<Set<number>>(() => new Set());
  // header: 执行结果 共 {steps.length} 步
  // map steps: button row with label, status icon, formatDuration(duration_ms), chevron
  // expanded => summary + TraceStepDetail
}
```

CSS classes: `.ask-exec-card`, `.ask-exec-step`, `.ask-exec-step-meta` — soft panel, rounded rows; reuse existing teal/green success colors from admin theme (no purple glow redesign).

- [ ] **Step 4: PASS** `npm test -- src/components/AskExecutionCard.test.tsx`

- [ ] **Step 5: Commit**

```bash
git add web/src/components/AskExecutionCard.tsx web/src/components/AskExecutionCard.test.tsx web/src/styles/global.css
git commit -m "feat: add AskExecutionCard with collapsible timed steps"
```

---

### Task 4: Chat shell — `AskMessageBubble` + `AskPage`

**Files:**
- Create: `web/src/components/AskMessageBubble.tsx`
- Modify: `web/src/pages/AskPage.tsx` (replace form+result cards with chat layout)
- Modify: `web/src/styles/global.css` (`.ask-chat-*`)
- Modify: `web/src/api/ask.ts` only if needed (already supports `sessionId`)

**Interfaces:**
- Message type (inline in AskPage or small `web/src/pages/askTypes.ts`):

```ts
export type AskChatMessage = {
  id: string;
  role: "user" | "assistant";
  text: string;
  createdAt: string;
  status?: "pending" | "ok" | "error";
  result?: AskResponse;
  error?: string;
};
```

- `AskMessageBubble` props: `{ message: AskChatMessage }`
- Assistant ok: `AskExecutionCard` + answer text + summary (置信度 / 检索模式 only) + footer `HH:mm:ss · 耗时 X`
- Assistant pending: 「执行中…」
- Assistant error: error string
- User: right-aligned bubble + time
- `AskPage`: on `kbId` change → new `sessionId = crypto.randomUUID()`, `messages=[]`
- Submit: append user + pending assistant; call `askQuestion({ knowledgeBaseId, question, sessionId, includeTrace: true, asOf? })`; fill assistant; on fail set error status
- Remove display of 核验状态 / competing claims / procedure_id from main summary (may remain inside step detail if present in trace)

- [ ] **Step 1: Rewrite failing AskPage tests first** (see Task 5 assertions) — or implement UI then fix tests in Task 5. **This plan: implement UI in Task 4, update tests in Task 5.**

- [ ] **Step 2: Implement `AskMessageBubble`**

```tsx
export function AskMessageBubble({ message }: { message: AskChatMessage }) {
  if (message.role === "user") {
    return (/* right bubble */);
  }
  // assistant: AskExecutionCard when result?.trace; answer; meta; duration
}
```

- [ ] **Step 3: Rewrite `AskPage` layout**

Structure:

```tsx
<section className="page-section ask-chat-page">
  <div className="ask-chat-messages">
    {messages.map((m) => <AskMessageBubble key={m.id} message={m} />)}
  </div>
  <form className="ask-chat-composer" onSubmit={...}>
    {/* question, as-of, send */}
  </form>
</section>
```

Keep `requestSequence` / ignore stale responses.

- [ ] **Step 4: Manual smoke** (optional): open `/ask`, ask twice, confirm two bubbles; switch KB clears.

- [ ] **Step 5: Commit**

```bash
git add web/src/components/AskMessageBubble.tsx web/src/pages/AskPage.tsx web/src/styles/global.css
git commit -m "feat: rebuild Ask page as in-memory chat with execution cards"
```

---

### Task 5: Update AskPage / ask API tests

**Files:**
- Modify: `web/src/pages/AskPage.test.tsx`
- Modify: `web/src/api/ask.test.ts` if sessionId coverage missing

**Requirements to assert:**
1. Empty KB still EmptyState
2. After ask: answer text visible; `sessionId` string passed to `askQuestion`
3. Evidence text appears only after expanding a step that contains it (or via TraceStepDetail)—if evidence only in `result.evidence` not in trace detail, show evidence inside expanded retrieve/verify via rendering `EvidenceList` under expanded card **or** map evidence into verify detail on client. **Simplest compliant approach:** when expanding any step, if `message.result.evidence` exists and step is `verify` or `retrieve`, also render `<EvidenceList evidence={...} />` once under that expansion. Spec: 证据进步骤展开 — implement EvidenceList under expanded `retrieve`/`verify` step.
4. No text「已核验」/「核验状态」in document after ask
5. Confidence (`90%`) and retrieval mode (`HYBRID`) visible
6. Duration from `duration_ms` visible
7. Second ask appends (two user questions visible)
8. Changing `kbId` clears messages (rerender with new useKb mock)

- [ ] **Step 1: Update tests to match chat UI labels** (`发送` or keep `提问` — **keep button label `提问`** for less churn)

Example call expectation:

```ts
expect(askQuestion).toHaveBeenCalledWith(
  expect.objectContaining({
    knowledgeBaseId: "kb-1",
    question: "定制商品可以退货吗？",
    includeTrace: true,
    sessionId: expect.any(String),
  }),
);
```

Remove assertions that require「存在冲突」/ verification badge.

- [ ] **Step 2: Run** `cd web && npm test -- src/pages/AskPage.test.tsx src/api/ask.test.ts src/components/AskExecutionCard.test.tsx`

- [ ] **Step 3: Fix until PASS**

- [ ] **Step 4: Commit**

```bash
git add web/src/pages/AskPage.test.tsx web/src/api/ask.test.ts web/src/pages/AskPage.tsx web/src/components/AskMessageBubble.tsx
git commit -m "test: cover ask chat session memory and hide verification summary"
```

---

## Spec coverage checklist

| Spec item | Task |
|-----------|------|
| Chat multi-turn memory | 4, 5 |
| session_id UUID, clear on KB change | 4, 5 |
| Skip remember | 1 |
| Per-node duration_ms | 2 |
| Execution card, steps default collapsed | 3 |
| Evidence in step expand | 4, 5 |
| No verification in summary; confidence + mode | 4, 5 |
| Total duration footer | 4, 5 |
| Pending / error bubbles | 4 |
| No localStorage / no session list | 4 (non-goal) |

## Self-review notes

- No TBD placeholders; remember skip is explicit skipped trace
- `AskExecutionCard` cardOpen default `true` + empty step expansion matches screenshot 2 while satisfying「步骤默认折叠」
- Types: `AskChatMessage` defined in Task 4; tests in Task 5 use same fields
