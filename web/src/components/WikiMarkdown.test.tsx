import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { WikiMarkdown } from "./WikiMarkdown";

describe("WikiMarkdown", () => {
  afterEach(cleanup);

  it("navigates real wikilinks and ignores fake entity links", async () => {
    const user = userEvent.setup();
    const onNavigate = vi.fn();
    render(
      <WikiMarkdown
        markdown={"参见 [[售后/退换货流程|退换货流程]] 与 [[女装尺码L|女装尺码L]]。"}
        pageIds={new Set(["售后/退换货流程"])}
        onNavigate={onNavigate}
      />,
    );
    await user.click(screen.getByRole("link", { name: "退换货流程" }));
    expect(onNavigate).toHaveBeenCalledWith("售后/退换货流程");
    expect(screen.queryByRole("link", { name: "女装尺码L" })).not.toBeInTheDocument();
  });

  it("keeps wikilink pipes from splitting GFM table columns", () => {
    const markdown = [
      "| 产品 | 产品描述 | 额度范围 |",
      "| --- | --- | --- |",
      "| [[个人信用贷款|个人信用贷款]] | [[一种无需抵押的贷款|一种无需抵押的贷款]] | [[1万元-50万元|1万元-50万元]] |",
    ].join("\n");

    render(
      <WikiMarkdown
        markdown={markdown}
        pageIds={new Set(["个人信用贷款"])}
        onNavigate={vi.fn()}
      />,
    );

    const table = screen.getByRole("table");
    const row = within(table).getAllByRole("row")[1];
    const cells = within(row).getAllByRole("cell");
    expect(cells).toHaveLength(3);
    expect(within(cells[0]).getByRole("link", { name: "个人信用贷款" })).toBeInTheDocument();
    expect(cells[1]).toHaveTextContent("一种无需抵押的贷款");
    expect(cells[2]).toHaveTextContent("1万元-50万元");
    expect(screen.queryByText(/\[\[/)).not.toBeInTheDocument();
  });

  it("highlights query terms", () => {
    render(
      <WikiMarkdown
        markdown={"退款将在三个工作日内到账"}
        pageIds={new Set()}
        highlightQuery="退款"
        onNavigate={vi.fn()}
      />,
    );
    expect(screen.getByText("退款").tagName).toBe("MARK");
  });
});
