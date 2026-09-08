import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
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
  retrieval_mode: "hybrid",
  request_id: "r1",
  trace: [{ node: "retrieve", status: "ok" as const, summary: "ok" }],
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

  it("does not expose or send the unsupported as-of option", async () => {
    const user = userEvent.setup();
    render(<AskPage />);

    await user.type(screen.getByLabelText("问题"), "历史政策是什么？");
    await user.click(screen.getByRole("button", { name: "提问" }));

    await waitFor(() => expect(askQuestion).toHaveBeenCalled());
    expect(screen.queryByLabelText("截至时间（可选）")).not.toBeInTheDocument();
    expect(screen.getByText("时间点查询将在后续版本开放")).toBeInTheDocument();
    expect(askQuestion.mock.calls[0][0]).not.toHaveProperty("asOf");
  });

  it("shows unavailable trace fallback when response trace is empty", async () => {
    const user = userEvent.setup();
    askQuestion.mockResolvedValue({ ...answer, trace: null });
    fetchTrace.mockRejectedValue(new Error("404"));
    render(<AskPage />);

    await user.type(screen.getByLabelText("问题"), "问题");
    await user.click(screen.getByRole("button", { name: "提问" }));

    expect(await screen.findByText("轨迹暂不可用")).toBeInTheDocument();
    expect(fetchTrace).toHaveBeenCalledWith("kb-1", "r1");
  });

  it("fetches trace by request_id when ask response omits trace", async () => {
    const user = userEvent.setup();
    askQuestion.mockResolvedValue({ ...answer, trace: null });
    fetchTrace.mockResolvedValue([{ node: "answer", status: "ok" as const, summary: "done" }]);
    render(<AskPage />);

    await user.type(screen.getByLabelText("问题"), "问题");
    await user.click(screen.getByRole("button", { name: "提问" }));

    expect(await screen.findByText("answer")).toBeInTheDocument();
    expect(fetchTrace).toHaveBeenCalledWith("kb-1", "r1");
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
