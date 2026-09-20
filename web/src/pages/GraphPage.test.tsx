import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { GraphPage } from "./GraphPage";

const {
  fetchGraphSnapshot,
  listGraphEntities,
  listGraphPredicates,
  fetchGraphNeighbors,
  retrieveGraph,
  useKb,
} = vi.hoisted(() => ({
  fetchGraphSnapshot: vi.fn(),
  listGraphEntities: vi.fn(),
  listGraphPredicates: vi.fn(),
  fetchGraphNeighbors: vi.fn(),
  retrieveGraph: vi.fn(),
  useKb: vi.fn(),
}));

vi.mock("../api/graph", () => ({
  fetchGraphSnapshot,
  listGraphEntities,
  listGraphPredicates,
  fetchGraphNeighbors,
  retrieveGraph,
}));

vi.mock("../app/KbContext", () => ({
  useKb,
}));

const entities = [
  { id: "e_rule", type: "RefundRule", name: "七天无理由" },
  { id: "e_seller", type: "Concept", name: "卖家" },
];

const edges = [
  {
    src: "e_rule",
    predicate: "运费承担方",
    dst: "e_seller",
    src_name: "七天无理由",
    dst_name: "卖家",
  },
];

describe("GraphPage", () => {
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    useKb.mockReturnValue({ kbId: "kb-1" });
    fetchGraphSnapshot.mockResolvedValue({ entities, edges, truncated: false, entity_total: 2 });
    listGraphEntities.mockResolvedValue([entities[0]]);
    listGraphPredicates.mockResolvedValue(["运费承担方"]);
    fetchGraphNeighbors.mockResolvedValue({
      entity_id: "e_rule",
      entities: [{ id: "e_seller", type: "Concept", name: "卖家" }],
      edges,
    });
    retrieveGraph.mockResolvedValue({
      query: "七天无理由运费",
      hit_count: 1,
      hits: [
        {
          score: 1,
          snippet: "七天无理由 运费承担方 卖家",
          claim_id: "c1",
          entity_id: "e_rule",
          src: "e_rule",
          dst: "e_seller",
          predicate: "运费承担方",
        },
      ],
      entities: entities,
      edges: edges,
    });
  });

  it("does not show entity list before search", async () => {
    render(
      <MemoryRouter>
        <GraphPage />
      </MemoryRouter>,
    );

    expect(await screen.findByRole("heading", { name: "知识图谱" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "七天无理由" })).not.toBeInTheDocument();
    expect(screen.getByText("输入实体名称或关系条件后点击搜索，结果将显示在此处。")).toBeInTheDocument();
    expect(screen.getByText("点击上方画布中的节点，此处将单独展示该节点及直接关联实体。")).toBeInTheDocument();
    await waitFor(() => {
      expect(fetchGraphSnapshot).toHaveBeenCalledWith("kb-1", { entityLimit: 200, edgeLimit: 500 });
    });
  });

  it("reloads snapshot with custom limits on refresh", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <GraphPage />
      </MemoryRouter>,
    );

    await screen.findByRole("heading", { name: "知识图谱" });
    await user.clear(screen.getByLabelText("实体上限（1–1000）"));
    await user.type(screen.getByLabelText("实体上限（1–1000）"), "50");
    await user.clear(screen.getByLabelText("边上限（1–5000）"));
    await user.type(screen.getByLabelText("边上限（1–5000）"), "80");
    await user.click(screen.getByRole("button", { name: "刷新" }));

    await waitFor(() => {
      expect(fetchGraphSnapshot).toHaveBeenLastCalledWith("kb-1", { entityLimit: 50, edgeLimit: 80 });
    });
  });

  it("runs graph retrieve and selects hit entity", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <GraphPage />
      </MemoryRouter>,
    );

    await screen.findByRole("heading", { name: "知识图谱" });
    await user.type(screen.getByLabelText("检索文本"), "七天无理由运费");
    await user.click(screen.getByRole("button", { name: "试跑检索" }));

    expect(await screen.findByText(/图谱检索返回 1 条关系，右侧已切换为检索子图/)).toBeInTheDocument();
    expect(retrieveGraph).toHaveBeenCalledWith("kb-1", "七天无理由运费", { topK: 20 });
    await waitFor(() => {
      expect(fetchGraphNeighbors).toHaveBeenCalledWith("kb-1", "e_rule");
    });
    expect(screen.getByText(/右侧当前为图谱检索子图/)).toBeInTheDocument();
  });

  it("loads focus view after selecting an entity from search", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <GraphPage />
      </MemoryRouter>,
    );

    await screen.findByRole("heading", { name: "知识图谱" });
    await user.type(screen.getByLabelText("实体名称 / ID"), "七天");
    await user.click(screen.getByRole("button", { name: "搜索" }));
    await user.click(await screen.findByRole("button", { name: /七天无理由/ }));

    await waitFor(() => {
      expect(fetchGraphNeighbors).toHaveBeenCalledWith("kb-1", "e_rule");
    });
    expect(await screen.findByRole("img", { name: "七天无理由 的关联子图" })).toBeInTheDocument();
  });

  it("expands neighbors for selected entity", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <GraphPage />
      </MemoryRouter>,
    );

    await screen.findByRole("heading", { name: "知识图谱" });
    await user.type(screen.getByLabelText("实体名称 / ID"), "七天");
    await user.click(screen.getByRole("button", { name: "搜索" }));
    await user.click(await screen.findByRole("button", { name: /七天无理由/ }));
    await user.click(screen.getByRole("button", { name: "展开邻居" }));

    await waitFor(() => {
      expect(fetchGraphNeighbors).toHaveBeenCalled();
    });
    expect(await screen.findByText("已展开 1 条关系。")).toBeInTheDocument();
  });
});
