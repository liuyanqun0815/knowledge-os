import { act, cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "../App";
import { AskPage } from "./AskPage";

const { askQuestion, fetchTrace, useKb } = vi.hoisted(() => ({
  askQuestion: vi.fn(),
  fetchTrace: vi.fn(),
  useKb: vi.fn(),
}));

vi.mock("../api/ask", () => ({ askQuestion, fetchTrace }));
vi.mock("../app/KbContext", () => ({ useKb }));

const answer = {
  text: "不可退货",
  claim_ids: ["c1"],
  evidence: [{ claim_id: "c1", span: "定制商品不适用七天无理由" }],
  confidence: 0.9,
  retrieval_mode: "HYBRID",
  verification_status: "verified",
  competing_claim_ids: [],
  procedure_id: null,
  as_of: null,
  request_id: "r1",
  duration_ms: 1500,
  trace: [
    { node: "retrieve", status: "ok" as const, summary: "ok", duration_ms: 800 },
    { node: "verify", status: "ok" as const, summary: "verified", duration_ms: 200 },
  ],
};

describe("AskPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useKb.mockReturnValue({ kbId: "kb-1", setKbId: vi.fn(), clearKb: vi.fn() });
    askQuestion.mockResolvedValue(answer);
    fetchTrace.mockResolvedValue([]);
  });

  afterEach(cleanup);

  it("shows empty state when no knowledge base is selected", () => {
    useKb.mockReturnValue({ kbId: null, setKbId: vi.fn(), clearKb: vi.fn() });

    render(<AskPage />);

    expect(screen.getByText(/请先选择知识库/)).toBeInTheDocument();
  });

  it("shows answer, sessionId, confidence, mode, duration; evidence only after expand", async () => {
    const user = userEvent.setup();
    render(<AskPage />);

    await user.type(screen.getByLabelText("问题"), "定制商品可以退货吗？");
    await user.click(screen.getByRole("button", { name: "发送" }));

    expect(await screen.findByText("不可退货")).toBeInTheDocument();
    expect(askQuestion).toHaveBeenCalledWith(
      expect.objectContaining({
        knowledgeBaseId: "kb-1",
        question: "定制商品可以退货吗？",
        includeTrace: true,
        sessionId: expect.any(String),
      }),
    );

    expect(screen.queryByText("定制商品不适用七天无理由")).not.toBeInTheDocument();
    expect(screen.queryByText(/已核验/)).not.toBeInTheDocument();
    expect(screen.queryByText(/核验状态/)).not.toBeInTheDocument();

    expect(screen.getByText("90%")).toBeInTheDocument();
    expect(screen.getByText("HYBRID")).toBeInTheDocument();
    expect(screen.getByText(/1\.50 秒|1500/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /执行结果/ }));
    expect(screen.getByText(/混合检索|retrieve/)).toBeInTheDocument();
    expect(screen.getByText(/Claim 核验|verify/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /混合检索|retrieve/ }));
    expect(screen.queryByText("定制商品不适用七天无理由")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Claim 核验|verify/ }));
    expect(screen.getByText("定制商品不适用七天无理由")).toBeInTheDocument();
  });

  it("does not expose as_of datetime control in the chat composer", () => {
    render(<AskPage />);
    expect(screen.queryByLabelText("截至时间（可选）")).not.toBeInTheDocument();
  });

  it("does not show verification summary after asking", async () => {
    const user = userEvent.setup();
    askQuestion.mockResolvedValue({
      ...answer,
      verification_status: "conflict",
      competing_claim_ids: ["c2", "c3"],
      procedure_id: "proc-42",
      as_of: "2024-06-15T06:30:00.000Z",
    });
    render(<AskPage />);

    await user.type(screen.getByLabelText("问题"), "运费谁承担？");
    await user.click(screen.getByRole("button", { name: "发送" }));

    expect(await screen.findByText("不可退货")).toBeInTheDocument();
    expect(screen.queryByText("存在冲突")).not.toBeInTheDocument();
    expect(screen.queryByText(/已核验/)).not.toBeInTheDocument();
    expect(screen.queryByText(/核验状态/)).not.toBeInTheDocument();
    expect(screen.queryByText("c2, c3")).not.toBeInTheDocument();
    expect(screen.getByText("90%")).toBeInTheDocument();
    expect(screen.getByText("HYBRID")).toBeInTheDocument();
  });

  it("appends a second ask so two user questions are visible", async () => {
    const user = userEvent.setup();
    render(<AskPage />);

    await user.type(screen.getByLabelText("问题"), "第一个问题");
    await user.click(screen.getByRole("button", { name: "发送" }));
    expect(await screen.findByText("不可退货")).toBeInTheDocument();

    askQuestion.mockResolvedValue({ ...answer, text: "第二个回答" });
    await user.type(screen.getByLabelText("问题"), "第二个问题");
    await user.click(screen.getByRole("button", { name: "发送" }));

    expect(await screen.findByText("第二个回答")).toBeInTheDocument();
    const log = screen.getByRole("log");
    expect(within(log).getByText("第一个问题")).toBeInTheDocument();
    expect(within(log).getByText("第二个问题")).toBeInTheDocument();
  });

  it("shows unavailable trace fallback when response trace is empty", async () => {
    const user = userEvent.setup();
    askQuestion.mockResolvedValue({ ...answer, trace: null });
    fetchTrace.mockRejectedValue(new Error("404"));
    render(<AskPage />);

    await user.type(screen.getByLabelText("问题"), "问题");
    await user.click(screen.getByRole("button", { name: "发送" }));

    expect(await screen.findByText("不可退货")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /执行结果/ }));
    expect(await screen.findByText("轨迹暂不可用")).toBeInTheDocument();
    expect(fetchTrace).toHaveBeenCalledWith("kb-1", "r1");
  });

  it("fetches trace by request_id when ask response omits trace", async () => {
    const user = userEvent.setup();
    askQuestion.mockResolvedValue({ ...answer, trace: null });
    fetchTrace.mockResolvedValue([{ node: "answer", status: "ok" as const, summary: "done" }]);
    render(<AskPage />);

    await user.type(screen.getByLabelText("问题"), "问题");
    await user.click(screen.getByRole("button", { name: "发送" }));

    expect(await screen.findByText("不可退货")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /执行结果/ }));
    expect(await screen.findByText(/生成回答|answer/)).toBeInTheDocument();
    expect(fetchTrace).toHaveBeenCalledWith("kb-1", "r1");
  });

  it("clears messages when kbId changes", async () => {
    const user = userEvent.setup();
    const view = render(<AskPage />);
    await user.type(screen.getByLabelText("问题"), "换库前的问题");
    await user.click(screen.getByRole("button", { name: "发送" }));
    expect(await screen.findByText("不可退货")).toBeInTheDocument();
    expect(within(screen.getByRole("log")).getByText("换库前的问题")).toBeInTheDocument();

    useKb.mockReturnValue({ kbId: "kb-2", setKbId: vi.fn(), clearKb: vi.fn() });
    view.rerender(<AskPage />);

    expect(screen.queryByText("不可退货")).not.toBeInTheDocument();
    expect(screen.queryByText("换库前的问题")).not.toBeInTheDocument();
  });

  it("ignores a pending answer after kbId changes", async () => {
    const user = userEvent.setup();
    let resolveAnswer: (value: typeof answer) => void = () => undefined;
    askQuestion.mockReturnValue(
      new Promise((resolve) => {
        resolveAnswer = resolve;
      }),
    );
    const view = render(<AskPage />);
    await user.type(screen.getByLabelText("问题"), "问题");
    await user.click(screen.getByRole("button", { name: "发送" }));

    useKb.mockReturnValue({ kbId: "kb-2", setKbId: vi.fn(), clearKb: vi.fn() });
    view.rerender(<AskPage />);
    await act(async () => {
      resolveAnswer(answer);
      await Promise.resolve();
    });

    expect(screen.queryByText("不可退货")).not.toBeInTheDocument();
  });

  it("wires the ask page into the application router", () => {
    render(
      <MemoryRouter initialEntries={["/ask"]} future={{ v7_relativeSplatPath: true, v7_startTransition: true }}>
        <App />
      </MemoryRouter>,
    );

    expect(screen.getByRole("textbox", { name: "问题" })).toBeInTheDocument();
  });
});
