import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "../App";
import { KbProvider } from "../app/KbContext";

const { createKnowledgeBase, getKnowledgeBase, listKnowledgeBases, updateKnowledgeBase } = vi.hoisted(() => ({
  createKnowledgeBase: vi.fn(),
  getKnowledgeBase: vi.fn(),
  listKnowledgeBases: vi.fn(),
  updateKnowledgeBase: vi.fn(),
}));

vi.mock("../api/knowledgeBases", () => ({
  createKnowledgeBase,
  getKnowledgeBase,
  listKnowledgeBases,
  updateKnowledgeBase,
}));

const knowledgeBase = {
  id: "kb-1",
  name: "电商客服",
  domain_type: "ecommerce_cs",
  description: "客服知识",
  status: "active" as const,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-02T00:00:00Z",
};

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]} future={{ v7_relativeSplatPath: true, v7_startTransition: true }}>
      <KbProvider>
        <App />
      </KbProvider>
    </MemoryRouter>,
  );
}

describe("knowledge base pages", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
    listKnowledgeBases.mockResolvedValue([knowledgeBase]);
    getKnowledgeBase.mockImplementation(async (id) =>
      id === "kb-new" ? { ...knowledgeBase, id, name: "企业文化" } : knowledgeBase,
    );
    createKnowledgeBase.mockResolvedValue({ ...knowledgeBase, id: "kb-new", name: "企业文化" });
    updateKnowledgeBase.mockImplementation(async (_id, body) => ({ ...knowledgeBase, ...body }));
  });

  it("renders knowledge base names and sets the current knowledge base", async () => {
    const user = userEvent.setup();
    renderAt("/knowledge-bases");

    const table = await screen.findByRole("table");
    expect(within(table).getByText("电商客服")).toBeInTheDocument();
    expect(within(table).getByText("ecommerce_cs")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "设为当前" }));

    expect(localStorage.getItem("akos_current_kb")).toBe("kb-1");
  });

  it("creates a knowledge base and opens its detail page", async () => {
    const user = userEvent.setup();
    renderAt("/knowledge-bases/new");

    await user.type(screen.getByLabelText("名称"), "企业文化");
    await user.selectOptions(screen.getByLabelText("领域类型"), "corporate_culture");
    await user.type(screen.getByLabelText("描述"), "公司价值观");
    await user.click(screen.getByRole("button", { name: "创建知识库" }));

    expect(createKnowledgeBase).toHaveBeenCalledWith({
      name: "企业文化",
      domain_type: "corporate_culture",
      description: "公司价值观",
    });
    expect(localStorage.getItem("akos_current_kb")).toBe("kb-new");
    expect(await screen.findByRole("heading", { name: "企业文化" })).toBeInTheDocument();
  });

  it("updates and archives a knowledge base after confirmation", async () => {
    const user = userEvent.setup();
    vi.spyOn(window, "confirm").mockReturnValue(true);
    renderAt("/knowledge-bases/kb-1");

    const nameInput = await screen.findByLabelText("名称");
    await user.clear(nameInput);
    await user.type(nameInput, "售后客服");
    await user.click(screen.getByRole("button", { name: "保存修改" }));

    expect(updateKnowledgeBase).toHaveBeenCalledWith("kb-1", {
      name: "售后客服",
      description: "客服知识",
    });

    await user.click(screen.getByRole("button", { name: "归档知识库" }));

    await waitFor(() => {
      expect(updateKnowledgeBase).toHaveBeenCalledWith("kb-1", { status: "archived" });
    });
    expect(screen.getByRole("link", { name: "管理文档" })).toHaveAttribute("href", "/sources?kb=kb-1");
    expect(screen.getByRole("link", { name: "开始问答" })).toHaveAttribute("href", "/ask?kb=kb-1");
  });
});
