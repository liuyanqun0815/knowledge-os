import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "../App";
import { QuarantinePage } from "./QuarantinePage";

const { listQuarantine, approveQuarantine, approveAllQuarantine, useKb } = vi.hoisted(() => ({
  listQuarantine: vi.fn(),
  approveQuarantine: vi.fn(),
  approveAllQuarantine: vi.fn(),
  useKb: vi.fn(),
}));

vi.mock("../api/quarantine", () => ({
  listQuarantine,
  approveQuarantine,
  approveAllQuarantine,
}));

vi.mock("../app/KbContext", () => ({
  useKb,
}));

const quarantineItems = [
  {
    id: 42,
    reason: "置信度过低",
    raw: { subject: "七天无理由", predicate: "适用对象", object: "特殊商品" },
  },
  {
    id: 43,
    reason: "invalid_predicate",
    raw: { subject: "定制商品", predicate: "适用对象", object: "特殊商品" },
  },
];

const quarantineItem = quarantineItems[0];

const approvedClaim = {
  id: "claim-1",
  family_id: "family-1",
  version: 1,
  subject: "七天无理由",
  predicate: "适用对象",
  object: "特殊商品",
  status: "active",
  valid_from: "2026-09-08T08:00:00Z",
  valid_to: null,
  source_ids: ["source-1"],
  subject_type: "RefundRule",
  object_type: "Concept",
  confidence: 0.75,
};

describe("QuarantinePage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useKb.mockReturnValue({ kbId: "kb-1", setKbId: vi.fn(), clearKb: vi.fn() });
    listQuarantine.mockResolvedValue([quarantineItem]);
    approveQuarantine.mockResolvedValue({ claim: approvedClaim });
    approveAllQuarantine.mockResolvedValue({
      approved_count: 2,
      failed_count: 0,
      claims: [approvedClaim, approvedClaim],
      failures: [],
    });
    vi.spyOn(window, "confirm").mockReturnValue(true);
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("shows empty state when no kb selected", () => {
    useKb.mockReturnValue({ kbId: null, setKbId: vi.fn(), clearKb: vi.fn() });

    render(<QuarantinePage />);

    expect(screen.getByText(/请先选择知识库/)).toBeInTheDocument();
    expect(listQuarantine).not.toHaveBeenCalled();
  });

  it("lists quarantine items with id, reason, and collapsed raw JSON", async () => {
    render(<QuarantinePage />);

    const table = await screen.findByRole("table");
    expect(within(table).getByText("42")).toBeInTheDocument();
    expect(within(table).getByText("置信度过低")).toBeInTheDocument();
    expect(within(table).getByText("查看 JSON")).toBeInTheDocument();
    expect(listQuarantine).toHaveBeenCalledWith("kb-1");
  });

  it("approves all quarantine items after confirm, reloads list, and shows success message", async () => {
    const user = userEvent.setup();
    listQuarantine.mockResolvedValueOnce(quarantineItems).mockResolvedValueOnce([]);

    render(<QuarantinePage />);
    await screen.findByText("42");

    await user.click(screen.getByRole("button", { name: "一键审批" }));

    expect(window.confirm).toHaveBeenCalledWith("确认批准当前 2 条隔离项吗？");
    expect(approveAllQuarantine).toHaveBeenCalledWith("kb-1");
    await waitFor(() => {
      expect(listQuarantine).toHaveBeenCalledTimes(2);
    });
    expect(screen.getByText("已批准 2 条隔离项。")).toBeInTheDocument();
  });

  it("does not approve all when confirm is cancelled", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(false);
    const user = userEvent.setup();
    listQuarantine.mockResolvedValue(quarantineItems);

    render(<QuarantinePage />);
    await screen.findByText("42");

    await user.click(screen.getByRole("button", { name: "一键审批" }));

    expect(approveAllQuarantine).not.toHaveBeenCalled();
  });

  it("shows error banner when approve all fails", async () => {
    approveAllQuarantine.mockRejectedValue(new Error("approve all failed"));
    const user = userEvent.setup();
    listQuarantine.mockResolvedValue(quarantineItems);

    render(<QuarantinePage />);
    await screen.findByText("42");

    await user.click(screen.getByRole("button", { name: "一键审批" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("一键审批失败，请稍后重试。");
  });

  it("approves quarantine after confirm, reloads list, and shows success message", async () => {
    const user = userEvent.setup();
    listQuarantine.mockResolvedValueOnce([quarantineItem]).mockResolvedValueOnce([]);

    render(<QuarantinePage />);
    await screen.findByText("42");

    await user.click(screen.getByRole("button", { name: "批准" }));

    expect(window.confirm).toHaveBeenCalledWith("确认批准隔离项 #42 吗？");
    expect(approveQuarantine).toHaveBeenCalledWith("kb-1", 42);
    await waitFor(() => {
      expect(listQuarantine).toHaveBeenCalledTimes(2);
    });
    expect(screen.getByText("隔离项 #42 已批准。")).toBeInTheDocument();
  });

  it("does not approve when confirm is cancelled", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(false);
    const user = userEvent.setup();

    render(<QuarantinePage />);
    await screen.findByText("42");

    await user.click(screen.getByRole("button", { name: "批准" }));

    expect(approveQuarantine).not.toHaveBeenCalled();
  });

  it("shows error banner when approve fails", async () => {
    approveQuarantine.mockRejectedValue(new Error("approve failed"));
    const user = userEvent.setup();

    render(<QuarantinePage />);
    await screen.findByText("42");

    await user.click(screen.getByRole("button", { name: "批准" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("隔离项批准失败，请稍后重试。");
  });

  it("wires the quarantine page into the application router", async () => {
    render(
      <MemoryRouter initialEntries={["/quarantine"]} future={{ v7_relativeSplatPath: true, v7_startTransition: true }}>
        <App />
      </MemoryRouter>,
    );

    expect(await screen.findByRole("heading", { name: "隔离审批" })).toBeInTheDocument();
  });
});
