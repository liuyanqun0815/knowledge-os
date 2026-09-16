import { cleanup, render, screen, within } from "@testing-library/react";
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
      expect.stringContaining("混合检索"),
      expect.stringContaining("生成回答"),
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
    await user.click(screen.getByRole("button", { name: /混合检索/ }));
    expect(screen.getByText(/"query": "退货"/)).toBeInTheDocument();
  });

  it("renders chunk hit table for retrieve step", async () => {
    const user = userEvent.setup();
    render(
      <TraceTimeline
        steps={[
          {
            node: "retrieve",
            status: "ok",
            detail: {
              chunk_hit_items: [
                {
                  hit_type: "chunk",
                  chunk_id: "chunk-1",
                  source_id: "source-1",
                  chunk_index: 0,
                  title: "退货说明",
                  score: 0.82,
                  snippet: "七天无理由",
                },
              ],
            },
          },
        ]}
      />,
    );

    await user.click(screen.getByRole("button", { name: /混合检索/ }));
    const table = screen.getByRole("table");
    expect(within(table).getByText((text) => text.includes("退货说明"))).toBeInTheDocument();
    expect(within(table).getByText("七天无理由")).toBeInTheDocument();
  });
});
