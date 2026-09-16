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
    expect(within(table).getByText("检索分")).toBeInTheDocument();
  });

  it("labels rerank scores as fusion vs relevance", async () => {
    const user = userEvent.setup();
    render(
      <TraceTimeline
        steps={[
          {
            node: "rerank",
            status: "ok",
            detail: {
              input_hits: [
                {
                  hit_type: "claim",
                  claim_id: "claim-abc12345",
                  score: 0.0167,
                  snippet: "个人信用贷款 定义",
                },
              ],
              output_hits: [
                {
                  hit_type: "claim",
                  claim_id: "claim-abc12345",
                  score: 0.81,
                  snippet: "个人信用贷款 定义",
                },
              ],
            },
          },
        ]}
      />,
    );

    await user.click(screen.getByRole("button", { name: /相关性重排/ }));
    expect(screen.getByText("融合分")).toBeInTheDocument();
    expect(screen.getByText("相关性分")).toBeInTheDocument();
    expect(screen.getAllByText(/Claim claim-ab/).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/加权 RRF/)).toBeInTheDocument();
  });

  it("shows normalize input/output and recall episodes", async () => {
    const user = userEvent.setup();
    render(
      <TraceTimeline
        steps={[
          {
            node: "normalize",
            status: "ok",
            summary: "问题已归一化",
            detail: {
              input: "七天无理由",
              output: "7天无理由",
              changed: true,
              replacements: [{ from: "七天", to: "7天" }],
            },
          },
          {
            node: "recall",
            status: "ok",
            summary: "召回 1 条历史会话",
            detail: {
              session_id: "sess-1",
              episode_count: 1,
              episodes: [{ q: "能否退货", a: "看类目" }],
            },
          },
        ]}
      />,
    );

    await user.click(screen.getByRole("button", { name: /问题归一化/ }));
    expect(screen.getByText("输入")).toBeInTheDocument();
    expect(screen.getByText("七天无理由")).toBeInTheDocument();
    expect(screen.getByText("7天无理由")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /会话回忆/ }));
    expect(screen.getByText("历史会话")).toBeInTheDocument();
    expect(screen.getByText("能否退货")).toBeInTheDocument();
    expect(screen.getByText("看类目")).toBeInTheDocument();
  });
});
