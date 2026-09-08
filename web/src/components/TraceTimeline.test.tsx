import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";
import { TraceTimeline } from "./TraceTimeline";

describe("TraceTimeline", () => {
  afterEach(cleanup);

  it("renders node names in order", () => {
    render(
      <TraceTimeline
        steps={[
          { node: "retrieve", status: "ok", summary: "hit 3" },
          { node: "answer", status: "ok", summary: "done" },
        ]}
      />,
    );

    expect(screen.getAllByRole("listitem").map((item) => item.textContent)).toEqual([
      expect.stringContaining("retrieve"),
      expect.stringContaining("answer"),
    ]);
  });

  it("shows fallback when steps empty", () => {
    render(<TraceTimeline steps={[]} unavailableReason="轨迹暂不可用" />);

    expect(screen.getByText("轨迹暂不可用")).toBeInTheDocument();
  });

  it("expands structured detail when clicked", async () => {
    const user = userEvent.setup();
    render(
      <TraceTimeline
        steps={[
          {
            node: "retrieve",
            status: "ok",
            detail: { query: "退货", hits: 3 },
          },
        ]}
      />,
    );

    expect(screen.queryByText(/"query": "退货"/)).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /retrieve/ }));
    expect(screen.getByText(/"query": "退货"/)).toBeInTheDocument();
  });
});
