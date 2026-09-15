import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "../App";
import { WikiPage } from "./WikiPage";

const { fetchWikiTree, fetchWikiPage, searchWiki, useKb, kbState } = vi.hoisted(() => {
  const kbState = { kbId: "kb1" as string | null };
  return {
    fetchWikiTree: vi.fn(),
    fetchWikiPage: vi.fn(),
    searchWiki: vi.fn(),
    useKb: vi.fn(),
    kbState,
  };
});

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

function WikiTestRoot({ kbId, initialEntry = "/wiki?kb=kb1" }: { kbId: string | null; initialEntry?: string }) {
  kbState.kbId = kbId;
  return (
    <MemoryRouter
      initialEntries={[initialEntry]}
      future={{ v7_relativeSplatPath: true, v7_startTransition: true }}
    >
      <WikiPage />
    </MemoryRouter>
  );
}

function renderWiki(initialEntry = "/wiki?kb=kb1", kbId: string | null = "kb1") {
  return render(<WikiTestRoot kbId={kbId} initialEntry={initialEntry} />);
}

describe("WikiPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    kbState.kbId = "kb1";
    useKb.mockImplementation(() => ({
      kbId: kbState.kbId,
      setKbId: vi.fn(),
      clearKb: vi.fn(),
    }));
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
    renderWiki("/wiki", null);

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

  it("resets page when knowledge base changes", async () => {
    const kb2Tree = {
      kb_id: "kb2",
      wiki_root: "/tmp2",
      hubs: [
        {
          name: "产品",
          description: "产品文档",
          pages: [{ page_id: "产品/入门指南", title: "入门指南", summary: "快速上手" }],
        },
      ],
    };
    const kb2Page = {
      page_id: "产品/入门指南",
      title: "入门指南",
      path: "产品/入门指南.md",
      markdown: "# 入门\n\n欢迎使用。\n",
    };

    fetchWikiTree.mockImplementation((kbId: string) =>
      Promise.resolve(kbId === "kb2" ? kb2Tree : tree),
    );
    fetchWikiPage.mockImplementation((kbId: string, pageId: string) => {
      if (kbId === "kb2" && pageId === "产品/入门指南") {
        return Promise.resolve(kb2Page);
      }
      if (kbId === "kb1" && pageId === "售后/七天无理由退货") {
        return Promise.resolve(page);
      }
      return Promise.reject(new Error("not found"));
    });

    const { rerender } = render(<WikiTestRoot kbId="kb1" />);

    await waitFor(() =>
      expect(fetchWikiPage).toHaveBeenCalledWith("kb1", "售后/七天无理由退货"),
    );
    expect(await screen.findByText(/可申请退款/)).toBeInTheDocument();

    fetchWikiPage.mockClear();
    fetchWikiTree.mockClear();
    rerender(<WikiTestRoot kbId="kb2" />);

    await waitFor(() => expect(fetchWikiTree).toHaveBeenCalledWith("kb2"));
    await waitFor(() =>
      expect(fetchWikiPage).toHaveBeenCalledWith("kb2", "产品/入门指南"),
    );
    expect(fetchWikiPage).not.toHaveBeenCalledWith("kb2", "售后/七天无理由退货");
    expect(await screen.findByText(/欢迎使用/)).toBeInTheDocument();
    expect(screen.queryByText(/Wiki 页面加载失败/)).not.toBeInTheDocument();
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
