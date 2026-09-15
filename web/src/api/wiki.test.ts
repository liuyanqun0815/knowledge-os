import { beforeEach, describe, expect, it, vi } from "vitest";
import { fetchWikiPage, fetchWikiTree, searchWiki } from "./wiki";

const { apiFetch } = vi.hoisted(() => ({
  apiFetch: vi.fn(),
}));

vi.mock("./http", () => ({
  apiFetch,
}));

describe("wiki api", () => {
  beforeEach(() => {
    apiFetch.mockReset();
  });

  it("fetchWikiTree calls tree endpoint", async () => {
    apiFetch.mockResolvedValue({
      json: async () => ({ kb_id: "kb-1", wiki_root: "/wiki", hubs: [] }),
    });

    await fetchWikiTree("kb-1");

    expect(apiFetch).toHaveBeenCalledWith("/admin/knowledge-bases/kb-1/wiki/tree");
  });

  it("fetchWikiPage encodes pageId path segments", async () => {
    apiFetch.mockResolvedValue({
      json: async () => ({ page_id: "政策/发票政策", title: "发票政策", path: "", markdown: "" }),
    });

    await fetchWikiPage("kb-1", "政策/发票政策");

    expect(apiFetch).toHaveBeenCalledWith("/admin/knowledge-bases/kb-1/wiki/pages/%E6%94%BF%E7%AD%96/%E5%8F%91%E7%A5%A8%E6%94%BF%E7%AD%96");
  });

  it("searchWiki passes query and limit params", async () => {
    apiFetch.mockResolvedValue({
      json: async () => ({ query: "发票", total: 0, hits: [] }),
    });

    await searchWiki("kb-1", "发票", 10);

    expect(apiFetch).toHaveBeenCalledWith("/admin/knowledge-bases/kb-1/wiki/search?q=%E5%8F%91%E7%A5%A8&limit=10");
  });
});
