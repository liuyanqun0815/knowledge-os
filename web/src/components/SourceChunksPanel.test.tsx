import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { SourceChunksPanel } from "./SourceChunksPanel";

const { fetchSourceChunks } = vi.hoisted(() => ({
  fetchSourceChunks: vi.fn(),
}));

vi.mock("../api/sources", () => ({
  fetchSourceChunks,
}));

const chunk = {
  id: "chunk-1",
  source_id: "source-1",
  chunk_index: 0,
  title: "退货说明",
  summary: "七天无理由退货规则",
  text: "买家可在七天内申请退货。",
  start: 0,
  end: 12,
  section_path: ["售后"],
  topics: ["退货"],
  token_count: 8,
  status: "active",
  content_hash: "abc",
  created_at: "2026-09-08T08:00:00Z",
};

describe("SourceChunksPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    fetchSourceChunks.mockResolvedValue([chunk]);
  });

  afterEach(cleanup);

  it("loads and renders chunk list with expandable body", async () => {
    const user = userEvent.setup();
    render(<SourceChunksPanel kbId="kb-1" sourceId="source-1" />);

    expect(await screen.findByText(/退货说明/)).toBeInTheDocument();
    expect(screen.getByText(/共 1 段/)).toBeInTheDocument();
    expect(fetchSourceChunks).toHaveBeenCalledWith("kb-1", "source-1", "active");

    await user.click(screen.getByText(/退货说明/));
    expect(screen.getByText("买家可在七天内申请退货。")).toBeInTheDocument();
  });
});
