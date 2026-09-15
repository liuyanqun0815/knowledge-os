import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "../App";
import { SourcesPage } from "./SourcesPage";

const { deleteSource, deleteTree, listSources, moveSources, uploadSource, uploadTree, useKb } = vi.hoisted(() => ({
  deleteSource: vi.fn(),
  deleteTree: vi.fn(),
  listSources: vi.fn(),
  moveSources: vi.fn(),
  uploadSource: vi.fn(),
  uploadTree: vi.fn(),
  useKb: vi.fn(),
}));

vi.mock("../api/sources", () => ({
  deleteSource,
  deleteTree,
  listSources,
  moveSources,
  uploadSource,
  uploadTree,
}));

vi.mock("../app/KbContext", () => ({
  useKb,
}));

const source = {
  id: "source-1",
  filename: "guide.md",
  relative_path: "guide.md",
  directory: "/",
  claims_count: 2,
  created_at: "2026-09-08T08:00:00Z",
  compile_status: "succeeded" as const,
};

describe("sources page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useKb.mockReturnValue({ kbId: "kb-1", setKbId: vi.fn(), clearKb: vi.fn() });
    listSources.mockResolvedValue([source]);
    uploadSource.mockResolvedValue({
      upload_mode: "single",
      files_total: 1,
      files_ingested: 1,
      files_skipped: 0,
      results: [
        {
          source_id: "source-2",
          path: "uploads/new.md",
          claims_created: 0,
          entities_upserted: 0,
          evidence_links: 0,
          quarantined: 0,
          errors: [],
        },
      ],
      errors: [],
    });
    uploadTree.mockResolvedValue({
      upload_mode: "tree",
      files_total: 1,
      files_ingested: 1,
      files_skipped: 0,
      results: [],
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

    const tree = await screen.findByRole("tree");
    expect(within(tree).getByText(/guide.md/)).toBeInTheDocument();
    expect(within(tree).getByText("已完成")).toBeInTheDocument();
    expect(listSources).toHaveBeenCalledWith("kb-1", { query: "" });
  });

  it("uploads the selected file and refreshes the list", async () => {
    const user = userEvent.setup();
    render(<SourcesPage />);
    await screen.findByText(/guide.md/);
    const file = new File(["# New"], "new.md", { type: "text/markdown" });

    await user.upload(screen.getByLabelText("选择文件"), file);
    await user.click(screen.getByRole("button", { name: "上传" }));

    await waitFor(() => {
      expect(uploadSource).toHaveBeenCalledWith("kb-1", file);
    });
  });

  it("accepts a dropped file and reports upload failures", async () => {
    uploadSource.mockRejectedValue(new Error("network error"));
    render(<SourcesPage />);
    await screen.findByText(/guide.md/);
    const file = new File(["bad"], "bad.md", { type: "text/markdown" });

    fireEvent.drop(screen.getByTestId("source-drop-zone"), {
      dataTransfer: { files: [file] },
    });
    expect(screen.getByText("已选择：bad.md")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "上传" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("上传失败");
  });

  it("uploads a selected folder with browser relative paths", async () => {
    const user = userEvent.setup();
    render(<SourcesPage />);
    await screen.findByText(/guide.md/);
    const file = new File(["# Policy"], "refund.md", { type: "text/markdown" });
    Object.defineProperty(file, "webkitRelativePath", { value: "policies/refund.md" });

    await user.upload(screen.getByLabelText("选择文件夹"), file);
    await user.click(screen.getByRole("button", { name: "上传" }));

    await waitFor(() => {
      expect(uploadTree).toHaveBeenCalledWith("kb-1", [{ file, relativePath: "policies/refund.md" }]);
    });
  });

  it("wires the sources page into the application router", async () => {
    render(
      <MemoryRouter initialEntries={["/sources"]} future={{ v7_relativeSplatPath: true, v7_startTransition: true }}>
        <App />
      </MemoryRouter>,
    );

    expect(await screen.findByRole("heading", { name: "文档来源" })).toBeInTheDocument();
  });

  it("shows async accept banner and polls until compile finishes", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    uploadSource.mockResolvedValue({
      accepted_async: true,
      upload_mode: "single",
      files_total: 1,
      files_ingested: 1,
      files_skipped: 0,
      results: [{ source_id: "a", path: "a.md", claims_created: 0, entities_upserted: 0, evidence_links: 0, quarantined: 0, errors: [] }],
      errors: [],
    });
    listSources
      .mockResolvedValueOnce([source])
      .mockResolvedValueOnce([{ ...source, id: "a", filename: "a.md", compile_status: "pending" as const }])
      .mockResolvedValueOnce([{ ...source, id: "a", filename: "a.md", compile_status: "succeeded" as const }]);

    render(<SourcesPage />);
    await screen.findByText(/guide.md/);
    const file = new File(["# A"], "a.md", { type: "text/markdown" });

    await user.upload(screen.getByLabelText("选择文件"), file);
    await user.click(screen.getByRole("button", { name: "上传" }));

    expect(await screen.findByRole("status")).toHaveTextContent(/后台编译中/);
    await waitFor(() => {
      expect(listSources.mock.calls.length).toBeGreaterThanOrEqual(2);
    });
    await vi.advanceTimersByTimeAsync(2000);
    await waitFor(() => {
      expect(listSources.mock.calls.length).toBeGreaterThanOrEqual(3);
    });
  });
});
