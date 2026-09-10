import { beforeEach, describe, expect, it, vi } from "vitest";
import { fetchGraphNeighbors, fetchGraphSnapshot, listGraphEntities, listGraphPredicates } from "./graph";

const { apiFetch } = vi.hoisted(() => ({
  apiFetch: vi.fn(),
}));

vi.mock("./http", () => ({
  apiFetch,
}));

describe("graph api", () => {
  beforeEach(() => {
    apiFetch.mockReset();
  });

  it("fetchGraphSnapshot calls snapshot endpoint", async () => {
    apiFetch.mockResolvedValue({
      json: async () => ({ entities: [], edges: [], truncated: false, entity_total: 0 }),
    });

    await fetchGraphSnapshot("kb-1", { entityLimit: 100, edgeLimit: 200 });

    expect(apiFetch).toHaveBeenCalledWith("/admin/knowledge-bases/kb-1/graph/snapshot?entity_limit=100&edge_limit=200");
  });

  it("fetchGraphNeighbors calls neighbors endpoint", async () => {
    apiFetch.mockResolvedValue({
      json: async () => ({ entity_id: "e1", entities: [], edges: [] }),
    });

    await fetchGraphNeighbors("kb-1", "entity/a", { predicates: ["适用类目"] });

    expect(apiFetch).toHaveBeenCalledWith(
      "/admin/knowledge-bases/kb-1/graph/entities/entity%2Fa/neighbors?predicates=%E9%80%82%E7%94%A8%E7%B1%BB%E7%9B%AE",
    );
  });

  it("listGraphEntities supports entity and predicate filters", async () => {
    apiFetch.mockResolvedValue({
      json: async () => [],
    });

    await listGraphEntities("kb-1", { q: "卖家", predicate: "运费" });

    expect(apiFetch).toHaveBeenCalledWith(
      "/admin/knowledge-bases/kb-1/graph/entities?q=%E5%8D%96%E5%AE%B6&predicate=%E8%BF%90%E8%B4%B9",
    );
  });

  it("listGraphPredicates calls predicates endpoint", async () => {
    apiFetch.mockResolvedValue({
      json: async () => ["适用类目"],
    });

    await listGraphPredicates("kb-1", "适用");

    expect(apiFetch).toHaveBeenCalledWith("/admin/knowledge-bases/kb-1/graph/predicates?q=%E9%80%82%E7%94%A8");
  });
});
