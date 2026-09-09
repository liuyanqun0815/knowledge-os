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
  verification_status: "verified",
  competing_claim_ids: [],
  procedure_id: null,
  as_of: null,
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
      includeTrace: true,
    });
  });

  it("sends as_of as ISO when datetime-local is set", async () => {
    const user = userEvent.setup();
    render(<AskPage />);

    await user.type(screen.getByLabelText("问题"), "历史政策是什么？");
    await user.type(screen.getByLabelText("截至时间（可选）"), "2024-06-15T14:30");
    await user.click(screen.getByRole("button", { name: "提问" }));

    await waitFor(() => expect(askQuestion).toHaveBeenCalled());
    expect(askQuestion.mock.calls[0][0]).toMatchObject({
      knowledgeBaseId: "kb-1",
      question: "历史政策是什么？",
      includeTrace: true,
      asOf: new Date("2024-06-15T14:30").toISOString(),
    });
    expect(screen.queryByText("时间点查询将在后续版本开放")).not.toBeInTheDocument();
  });

  it("displays AnswerV2 meta fields after asking", async () => {
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
    await user.click(screen.getByRole("button", { name: "提问" }));

    expect(await screen.findByText("存在冲突")).toBeInTheDocument();
    expect(screen.getByText("c2, c3")).toBeInTheDocument();
    expect(screen.getByText("proc-42")).toBeInTheDocument();
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
