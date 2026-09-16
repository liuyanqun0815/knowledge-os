import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "../App";
import { ClaimsPage } from "./ClaimsPage";

const { listClaims, fetchClaimHistory, useKb } = vi.hoisted(() => ({
  listClaims: vi.fn(),
  fetchClaimHistory: vi.fn(),
  useKb: vi.fn(),
}));

vi.mock("../api/claims", () => ({
  listClaims,
  fetchClaimHistory,
}));

vi.mock("../app/KbContext", () => ({
  useKb,
}));

const claim = {
  id: "claim-1",
  family_id: "family-1",
  version: 2,
  subject: "七天无理由",
  predicate: "适用对象",
  object: "普通商品",
  status: "active",
  valid_from: "2026-09-08T08:00:00Z",
  valid_to: null,
  source_ids: ["source-1"],
  subject_type: "RefundRule",
  object_type: "Concept",
  confidence: 0.92,
};

const history = [
  {
    id: "claim-0",
    family_id: "family-1",
    version: 1,
    subject: "七天无理由",
    predicate: "适用对象",
    object: "全部商品",
    status: "superseded",
    valid_from: "2026-09-01T08:00:00Z",
    valid_to: "2026-09-08T08:00:00Z",
    source_ids: ["source-0"],
  },
  {
    id: "claim-1",
    family_id: "family-1",
    version: 2,
    subject: "七天无理由",
    predicate: "适用对象",
    object: "普通商品",
    status: "active",
    valid_from: "2026-09-08T08:00:00Z",
    valid_to: null,
    source_ids: ["source-1"],
  },
];

describe("ClaimsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useKb.mockReturnValue({ kbId: "kb-1", setKbId: vi.fn(), clearKb: vi.fn() });
    listClaims.mockResolvedValue([claim]);
    fetchClaimHistory.mockResolvedValue(history);
  });

  afterEach(cleanup);

  it("shows empty state when no kb selected", () => {
    useKb.mockReturnValue({ kbId: null, setKbId: vi.fn(), clearKb: vi.fn() });

    render(<ClaimsPage />);

    expect(screen.getByText(/请先选择知识库/)).toBeInTheDocument();
    expect(listClaims).not.toHaveBeenCalled();
  });

  it("lists claims with subject, predicate, object, status, version, and confidence", async () => {
    render(<ClaimsPage />);

    const table = await screen.findByRole("table");
    expect(within(table).getByText("七天无理由")).toBeInTheDocument();
    expect(within(table).getByText("适用对象")).toBeInTheDocument();
    expect(within(table).getByText("普通商品")).toBeInTheDocument();
    expect(within(table).getByText("生效")).toBeInTheDocument();
    expect(within(table).getByText("2")).toBeInTheDocument();
    expect(within(table).getByText("0.92")).toBeInTheDocument();
    expect(listClaims).toHaveBeenCalledWith("kb-1", {});
  });

  it("passes status and subject filters to listClaims", async () => {
    const user = userEvent.setup();
    render(<ClaimsPage />);
    await screen.findByText("七天无理由");

    await user.selectOptions(screen.getByLabelText("状态"), "active");
    await user.type(screen.getByLabelText("主体"), "七天");

    await waitFor(() => {
      expect(listClaims).toHaveBeenCalledWith("kb-1", { status: "active", subject: "七天" });
    });
  });

  it("expands claim history when a row is clicked", async () => {
    const user = userEvent.setup();
    render(<ClaimsPage />);
    await screen.findByText("七天无理由");

    await user.click(screen.getByText("普通商品"));

    expect(await screen.findByText("v1 · 七天无理由")).toBeInTheDocument();
    expect(screen.getByText("v2 · 七天无理由")).toBeInTheDocument();
    expect(fetchClaimHistory).toHaveBeenCalledWith("kb-1", "family-1");
  });

  it("paginates claims and navigates between pages", async () => {
    const user = userEvent.setup();
    const manyClaims = Array.from({ length: 25 }, (_, index) => ({
      ...claim,
      id: `claim-${index}`,
      family_id: `family-${index}`,
      subject: `主体-${index}`,
    }));
    listClaims.mockResolvedValue(manyClaims);

    render(<ClaimsPage />);
    await screen.findByText("主体-0");
    expect(screen.getByText("主体-9")).toBeInTheDocument();
    expect(screen.queryByText("主体-10")).not.toBeInTheDocument();
    expect(screen.getByText("共 25 条，第 1 / 3 页")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "下一页" }));

    expect(await screen.findByText("主体-10")).toBeInTheDocument();
    expect(screen.queryByText("主体-0")).not.toBeInTheDocument();
    expect(screen.getByText("共 25 条，第 2 / 3 页")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "下一页" }));

    expect(await screen.findByText("主体-20")).toBeInTheDocument();
    expect(screen.queryByText("主体-10")).not.toBeInTheDocument();
    expect(screen.getByText("共 25 条，第 3 / 3 页")).toBeInTheDocument();
  });

  it("wires the claims page into the application router", async () => {
    render(
      <MemoryRouter initialEntries={["/claims"]} future={{ v7_relativeSplatPath: true, v7_startTransition: true }}>
        <App />
      </MemoryRouter>,
    );

    expect(await screen.findByRole("heading", { name: "Claim 浏览" })).toBeInTheDocument();
  });
});
