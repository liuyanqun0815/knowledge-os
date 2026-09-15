import { cleanup, render, screen } from "@testing-library/react";
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
