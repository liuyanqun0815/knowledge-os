import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "../App";
import { WikiPage } from "./WikiPage";

const { fetchWikiTree, fetchWikiPage, searchWiki, useKb } = vi.hoisted(() => ({
  fetchWikiTree: vi.fn(),
  fetchWikiPage: vi.fn(),
  searchWiki: vi.fn(),
  useKb: vi.fn(),
}));

vi.mock("../api/wiki", () => ({ fetchWikiTree, fetchWikiPage, searchWiki }));
vi.mock("../app/KbContext", () => ({ useKb }));

const tree = {
  kb_id: "kb1",
  wiki_root: "/tmp",
  hubs: [
    {
      name: "售后",
      description: "涵盖退货",
      pages: [{ page_id: "售后/七天无理由退货", title: "七天无理由退货", summary: "退货政策" }],
    },
  ],
};

const page = {
  page_id: "售后/七天无理由退货",
  title: "七天无理由退货",
  path: "售后/七天无理由退货.md",
  markdown: "# 七天\n\n可申请退款。\n",
};

function renderWiki(initialEntry = "/wiki?kb=kb1") {
  return render(
    <MemoryRouter
      initialEntries={[initialEntry]}
      future={{ v7_relativeSplatPath: true, v7_startTransition: true }}
    >
      <WikiPage />
    </MemoryRouter>,
  );
}

describe("WikiPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useKb.mockReturnValue({ kbId: "kb1", setKbId: vi.fn(), clearKb: vi.fn() });
    fetchWikiTree.mockResolvedValue(tree);
    fetchWikiPage.mockResolvedValue(page);
    searchWiki.mockResolvedValue({
      query: "退款",
      total: 1,
      hits: [{ page_id: "售后/七天无理由退货", title: "七天无理由退货", snippets: ["可申请退款"] }],
    });
  });

  afterEach(cleanup);

  it("shows empty state when no knowledge base is selected", () => {
    useKb.mockReturnValue({ kbId: null, setKbId: vi.fn(), clearKb: vi.fn() });

    renderWiki("/wiki");

    expect(screen.getByText(/请先选择知识库/)).toBeInTheDocument();
  });

  it("renders tree and page content", async () => {
    renderWiki();

    expect(await screen.findByRole("button", { name: "七天无理由退货" })).toBeInTheDocument();
    await waitFor(() => expect(fetchWikiPage).toHaveBeenCalled());
    expect(await screen.findByText(/可申请退款/)).toBeInTheDocument();
  });

  it("loads search hits when q is present and keeps q when opening a hit", async () => {
    const user = userEvent.setup();
    renderWiki("/wiki?kb=kb1&q=%E9%80%80%E6%AC%BE");

    expect(await screen.findByText(/可申请退款/)).toBeInTheDocument();
    await waitFor(() => expect(searchWiki).toHaveBeenCalledWith("kb1", "退款"));

    await user.click(screen.getByRole("button", { name: /七天无理由退货/ }));
    await waitFor(() =>
      expect(fetchWikiPage).toHaveBeenCalledWith("kb1", "售后/七天无理由退货"),
    );
  });

  it("wires the wiki page into the application router", async () => {
    render(
      <MemoryRouter
        initialEntries={["/wiki"]}
        future={{ v7_relativeSplatPath: true, v7_startTransition: true }}
      >
        <App />
      </MemoryRouter>,
    );

    expect(await screen.findByRole("heading", { name: "Wiki" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Wiki" })).toBeInTheDocument();
  });
});
