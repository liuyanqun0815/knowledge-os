import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "../App";
import { KbProvider } from "../app/KbContext";

const { createKnowledgeBase, deleteKnowledgeBase, getKnowledgeBase, listKnowledgeBases, updateKnowledgeBase } = vi.hoisted(
  () => ({
    createKnowledgeBase: vi.fn(),
    deleteKnowledgeBase: vi.fn(),
    getKnowledgeBase: vi.fn(),
    listKnowledgeBases: vi.fn(),
    updateKnowledgeBase: vi.fn(),
  }),
);

vi.mock("../api/knowledgeBases", () => ({
  createKnowledgeBase,
  deleteKnowledgeBase,
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

const testKnowledgeBase = {
  id: "kb-test",
  name: "pg-knowledge-test",
  domain_type: "ecommerce_cs",
  description: "",
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
    deleteKnowledgeBase.mockImplementation(async (id) => {
      if (id === "kb-test") {
        return { ...testKnowledgeBase, status: "archived" as const };
      }
      return { ...knowledgeBase, status: "archived" as const };
    });
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

  it("deletes a knowledge base from the list after confirmation", async () => {
    const user = userEvent.setup();
    vi.spyOn(window, "confirm").mockReturnValue(true);
    let includeTestKb = true;
    listKnowledgeBases.mockImplementation(async () =>
      includeTestKb ? [knowledgeBase, testKnowledgeBase] : [knowledgeBase],
    );
    deleteKnowledgeBase.mockImplementation(async (id) => {
      includeTestKb = false;
      return id === "kb-test"
        ? { ...testKnowledgeBase, status: "archived" as const }
        : { ...knowledgeBase, status: "archived" as const };
    });
    renderAt("/knowledge-bases");

    const table = await screen.findByRole("table");
    expect(within(table).getByText("pg-knowledge-test")).toBeInTheDocument();

    const deleteButtons = within(table).getAllByRole("button", { name: "删除" });
    await user.click(deleteButtons[1]);

    await waitFor(() => {
      expect(deleteKnowledgeBase).toHaveBeenCalledWith("kb-test");
      expect(within(table).queryByText("pg-knowledge-test")).not.toBeInTheDocument();
    });
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
    await waitFor(() => expect(listKnowledgeBases).toHaveBeenCalledTimes(2));
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

    await user.click(screen.getByRole("button", { name: "删除知识库" }));

    await waitFor(() => {
      expect(updateKnowledgeBase).toHaveBeenCalledWith("kb-1", { status: "archived" });
    });
    await waitFor(() => expect(listKnowledgeBases).toHaveBeenCalledTimes(2));
    expect(screen.getByRole("link", { name: "管理文档" })).toHaveAttribute("href", "/sources?kb=kb-1");
    expect(screen.getByRole("link", { name: "开始问答" })).toHaveAttribute("href", "/ask?kb=kb-1");
    expect(screen.getByRole("link", { name: "打开 Wiki" })).toHaveAttribute("href", "/wiki?kb=kb-1");
    expect(screen.queryByRole("button", { name: "导出 Wiki" })).not.toBeInTheDocument();
  });
});
