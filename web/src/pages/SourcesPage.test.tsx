import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "../App";
import { SourcesPage } from "./SourcesPage";

const { listSources, uploadSource, useKb } = vi.hoisted(() => ({
  listSources: vi.fn(),
  uploadSource: vi.fn(),
  useKb: vi.fn(),
}));

vi.mock("../api/sources", () => ({
  listSources,
  uploadSource,
}));

vi.mock("../app/KbContext", () => ({
  useKb,
}));

const source = {
  id: "source-1",
  filename: "guide.md",
  created_at: "2026-09-08T08:00:00Z",
  compile_status: "succeeded" as const,
};

describe("sources page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useKb.mockReturnValue({ kbId: "kb-1", setKbId: vi.fn(), clearKb: vi.fn() });
    listSources.mockResolvedValue([source]);
    uploadSource.mockResolvedValue({
      source_id: "source-2",
      path: "uploads/new.md",
      claims_created: 0,
      entities_upserted: 0,
      evidence_links: 0,
      quarantined: 0,
      errors: [],
    });
  });

  afterEach(() => {
    cleanup();
    vi.useRealTimers();
  });

  it("shows empty state when no kb selected", () => {
    useKb.mockReturnValue({ kbId: null, setKbId: vi.fn(), clearKb: vi.fn() });

    render(<SourcesPage />);

    expect(screen.getByText(/请先选择知识库/)).toBeInTheDocument();
    expect(listSources).not.toHaveBeenCalled();
  });

  it("lists source filenames and compile statuses", async () => {
    render(<SourcesPage />);

    const table = await screen.findByRole("table");
    expect(within(table).getByText("guide.md")).toBeInTheDocument();
    expect(within(table).getByText("已完成")).toBeInTheDocument();
    expect(listSources).toHaveBeenCalledWith("kb-1");
  });

  it("ignores a stale source list after kbId changes", async () => {
    let resolveFirstRequest: (items: (typeof source)[]) => void = () => undefined;
    listSources
      .mockReturnValueOnce(
        new Promise((resolve) => {
          resolveFirstRequest = resolve;
        }),
      )
      .mockResolvedValueOnce([{ ...source, id: "source-2", filename: "new-kb.md" }]);

    const view = render(<SourcesPage />);
    useKb.mockReturnValue({ kbId: "kb-2", setKbId: vi.fn(), clearKb: vi.fn() });
    view.rerender(<SourcesPage />);

    expect(await screen.findByText("new-kb.md")).toBeInTheDocument();
    await act(async () => {
      resolveFirstRequest([{ ...source, filename: "old-kb.md" }]);
      await Promise.resolve();
    });

    expect(screen.queryByText("old-kb.md")).not.toBeInTheDocument();
    expect(screen.getByText("new-kb.md")).toBeInTheDocument();
  });

  it("uploads the selected file and refreshes the list", async () => {
    const user = userEvent.setup();
    render(<SourcesPage />);
    await screen.findByText("guide.md");
    const file = new File(["# New"], "new.md", { type: "text/markdown" });

    await user.upload(screen.getByLabelText("选择文档"), file);
    await user.click(screen.getByRole("button", { name: "上传文档" }));

    await waitFor(() => {
      expect(uploadSource).toHaveBeenCalledWith("kb-1", file, {});
    });
    expect(listSources).toHaveBeenCalledTimes(2);
  });

  it("passes replaces_source_id when provided and shows upload summary", async () => {
    uploadSource.mockResolvedValue({
      source_id: "source-3",
      path: "uploads/evolved.md",
      claims_created: 5,
      entities_upserted: 2,
      evidence_links: 4,
      quarantined: 1,
      errors: [],
    });
    const user = userEvent.setup();
    render(<SourcesPage />);
    await screen.findByText("guide.md");
    const file = new File(["# Evolved"], "evolved.md", { type: "text/markdown" });

    await user.upload(screen.getByLabelText("选择文档"), file);
    await user.type(screen.getByLabelText(/替换文档 ID/), "source-1");
    await user.click(screen.getByRole("button", { name: "上传文档" }));

    await waitFor(() => {
      expect(uploadSource).toHaveBeenCalledWith("kb-1", file, { replacesSourceId: "source-1" });
    });
    expect(screen.getByRole("status")).toHaveTextContent("新建 Claim 5 条");
    expect(screen.getByRole("status")).toHaveTextContent("隔离 1 条");
  });

  it("accepts a dropped file and reports upload failures", async () => {
    uploadSource.mockRejectedValue(new Error("network error"));
    render(<SourcesPage />);
    await screen.findByText("guide.md");
    const file = new File(["bad"], "bad.md", { type: "text/markdown" });

    fireEvent.drop(screen.getByTestId("source-drop-zone"), {
      dataTransfer: { files: [file] },
    });
    expect(screen.getByText("已选择：bad.md")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "上传文档" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("上传失败");
  });

  it("polls while compile_status is running and stops after completion", async () => {
    vi.useFakeTimers();
    listSources
      .mockResolvedValueOnce([{ ...source, compile_status: "running" }])
      .mockResolvedValueOnce([{ ...source, compile_status: "succeeded" }]);

    render(<SourcesPage />);
    await act(async () => {
      await Promise.resolve();
    });
    expect(screen.getByText("编译中")).toBeInTheDocument();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });
    expect(listSources).toHaveBeenCalledTimes(2);
    expect(screen.getByText("已完成")).toBeInTheDocument();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(4000);
    });
    expect(listSources).toHaveBeenCalledTimes(2);
  });

  it("wires the sources page into the application router", async () => {
    render(
      <MemoryRouter initialEntries={["/sources"]} future={{ v7_relativeSplatPath: true, v7_startTransition: true }}>
        <App />
      </MemoryRouter>,
    );

    expect(await screen.findByRole("heading", { name: "文档来源" })).toBeInTheDocument();
  });
});
