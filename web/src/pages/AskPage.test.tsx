import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "../App";
import { AskPage } from "./AskPage";

const { askQuestion, useKb } = vi.hoisted(() => ({
  askQuestion: vi.fn(),
  useKb: vi.fn(),
}));

vi.mock("../api/ask", () => ({ askQuestion }));
vi.mock("../app/KbContext", () => ({ useKb }));

const answer = {
  text: "不可退货",
  claim_ids: ["c1"],
  evidence: [{ claim_id: "c1", span: "定制商品不适用七天无理由" }],
  confidence: 0.9,
  retrieval_mode: "hybrid",
  request_id: "r1",
  trace: [{ node: "retrieve", status: "ok" as const, summary: "ok" }],
};

describe("AskPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useKb.mockReturnValue({ kbId: "kb-1", setKbId: vi.fn(), clearKb: vi.fn() });
    askQuestion.mockResolvedValue(answer);
  });

  afterEach(cleanup);

  it("shows empty state when no knowledge base is selected", () => {
    useKb.mockReturnValue({ kbId: null, setKbId: vi.fn(), clearKb: vi.fn() });

    render(<AskPage />);

    expect(screen.getByText(/请先选择知识库/)).toBeInTheDocument();
  });

  it("shows answer text, evidence, and response trace after asking", async () => {
    const user = userEvent.setup();
    render(<AskPage />);

    await user.type(screen.getByLabelText("问题"), "定制商品可以退货吗？");
    await user.click(screen.getByRole("button", { name: "提问" }));

    expect(await screen.findByText("不可退货")).toBeInTheDocument();
    expect(screen.getByText("定制商品不适用七天无理由")).toBeInTheDocument();
    expect(screen.getByText("retrieve")).toBeInTheDocument();
    expect(askQuestion).toHaveBeenCalledWith({
      knowledgeBaseId: "kb-1",
      question: "定制商品可以退货吗？",
    });
  });

  it("converts as-of time to an ISO string", async () => {
    const user = userEvent.setup();
    render(<AskPage />);

    await user.type(screen.getByLabelText("问题"), "历史政策是什么？");
    await user.type(screen.getByLabelText("截至时间（可选）"), "2026-09-08T10:30");
    await user.click(screen.getByRole("button", { name: "提问" }));

    await waitFor(() => expect(askQuestion).toHaveBeenCalled());
    expect(askQuestion.mock.calls[0][0].asOf).toBe(new Date("2026-09-08T10:30").toISOString());
  });

  it("shows unavailable trace fallback when response trace is empty", async () => {
    const user = userEvent.setup();
    askQuestion.mockResolvedValue({ ...answer, trace: null });
    render(<AskPage />);

    await user.type(screen.getByLabelText("问题"), "问题");
    await user.click(screen.getByRole("button", { name: "提问" }));

    expect(await screen.findByText("轨迹暂不可用")).toBeInTheDocument();
  });

  it("clears the previous result when kbId changes", async () => {
    const user = userEvent.setup();
    const view = render(<AskPage />);
    await user.type(screen.getByLabelText("问题"), "问题");
    await user.click(screen.getByRole("button", { name: "提问" }));
    expect(await screen.findByText("不可退货")).toBeInTheDocument();

    useKb.mockReturnValue({ kbId: "kb-2", setKbId: vi.fn(), clearKb: vi.fn() });
    view.rerender(<AskPage />);

    expect(screen.queryByText("不可退货")).not.toBeInTheDocument();
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
    await user.click(screen.getByRole("button", { name: "提问" }));

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
