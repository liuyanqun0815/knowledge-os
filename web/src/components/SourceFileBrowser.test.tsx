import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { SourceFileBrowser } from "./SourceFileBrowser";

const { deleteTree, fetchSourceContent, moveSources } = vi.hoisted(() => ({
  deleteTree: vi.fn(),
  fetchSourceContent: vi.fn(),
  moveSources: vi.fn(),
}));

vi.mock("../api/sources", () => ({
  deleteSource: vi.fn(),
  deleteTree,
  fetchSourceContent,
  moveSources,
}));

const sources = [
  {
    id: "source-1",
    filename: "one.md",
    relative_path: "policies/one.md",
    directory: "/policies",
    claims_count: 1,
    created_at: "2026-09-08T08:00:00Z",
    compile_status: "succeeded" as const,
  },
  {
    id: "source-2",
    filename: "two.md",
    relative_path: "policies/nested/two.md",
    directory: "/policies/nested",
    claims_count: 2,
    created_at: "2026-09-08T08:00:00Z",
    compile_status: "succeeded" as const,
  },
];

describe("source file browser", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    moveSources.mockResolvedValue([]);
    deleteTree.mockResolvedValue({ deleted_count: 2 });
    fetchSourceContent.mockResolvedValue({
      source_id: "source-1",
      title: "one.md",
      relative_path: "policies/one.md",
      content: "# One\nhello",
      size_bytes: 12,
      encoding: "utf-8",
    });
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("renders collapsible nested folders", async () => {
    const user = userEvent.setup();
    render(
      <SourceFileBrowser
        kbId="kb-1"
        sources={sources}
        searchQuery=""
        onSearchChange={vi.fn()}
        expandedSourceId={null}
        onToggleSource={vi.fn()}
        onChanged={vi.fn()}
        onError={vi.fn()}
      />,
    );

    expect(screen.queryByText(/one.md/)).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "展开文件夹 policies" }));
    expect(screen.getByText(/one.md/)).toBeInTheDocument();
    expect(screen.queryByText(/two.md/)).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "展开文件夹 nested" }));
    expect(screen.getByText(/two.md/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "收起文件夹 policies" }));
    expect(screen.queryByText(/one.md/)).not.toBeInTheDocument();
  });

  it("opens plain-text preview from filename or view button", async () => {
    const user = userEvent.setup();
    render(
      <SourceFileBrowser
        kbId="kb-1"
        sources={sources}
        searchQuery=""
        onSearchChange={vi.fn()}
        expandedSourceId={null}
        onToggleSource={vi.fn()}
        onChanged={vi.fn()}
        onError={vi.fn()}
      />,
    );

    await user.click(screen.getByRole("button", { name: "展开文件夹 policies" }));
    await user.click(screen.getByRole("button", { name: /📄 one\.md/ }));
    expect(await screen.findByRole("dialog")).toBeInTheDocument();
    expect(await screen.findByText((text) => text.includes("# One") && text.includes("hello"))).toBeInTheDocument();
    expect(fetchSourceContent).toHaveBeenCalledWith("kb-1", "source-1");

    await user.click(screen.getByRole("button", { name: "关闭预览" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());

    await user.click(screen.getByRole("button", { name: "查看文件 one.md" }));
    expect(await screen.findByRole("dialog")).toBeInTheDocument();
    expect(fetchSourceContent).toHaveBeenCalledTimes(2);
  });

  it("moves and deletes a folder using its relative path and document count", async () => {
    const user = userEvent.setup();
    const onChanged = vi.fn();
    vi.spyOn(window, "prompt").mockReturnValue("archive/");
    vi.spyOn(window, "confirm").mockReturnValue(true);
    render(
      <SourceFileBrowser
        kbId="kb-1"
        sources={sources}
        searchQuery=""
        onSearchChange={vi.fn()}
        expandedSourceId={null}
        onToggleSource={vi.fn()}
        onChanged={onChanged}
        onError={vi.fn()}
      />,
    );

    await user.click(screen.getByRole("button", { name: "移动文件夹 policies" }));
    expect(moveSources).toHaveBeenCalledWith("kb-1", "policies/", "archive/");

    await user.click(screen.getByRole("button", { name: "删除文件夹 policies" }));
    expect(window.confirm).toHaveBeenCalledWith("确认删除文件夹 policies（共 2 个文档）？");
    expect(deleteTree).toHaveBeenCalledWith("kb-1", "policies/");
    await waitFor(() => expect(onChanged).toHaveBeenCalledTimes(2));
  });
});
