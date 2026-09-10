import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { GraphFocusView } from "./GraphFocusView";

describe("GraphFocusView", () => {
  it("renders center node and neighbor edges", () => {
    render(
      <GraphFocusView
        center={{ id: "e_rule", type: "RefundRule", name: "七天无理由" }}
        entities={[
          { id: "e_rule", type: "RefundRule", name: "七天无理由" },
          { id: "e_seller", type: "Concept", name: "卖家" },
        ]}
        edges={[
          {
            src: "e_rule",
            predicate: "运费承担方",
            dst: "e_seller",
            src_name: "七天无理由",
            dst_name: "卖家",
          },
        ]}
        onSelect={vi.fn()}
      />,
    );

    expect(screen.getByRole("heading", { name: "关联视图" })).toBeInTheDocument();
    expect(screen.getAllByText("运费承担方").length).toBeGreaterThan(0);
    expect(screen.getByRole("img", { name: "七天无理由 的关联子图" })).toBeInTheDocument();
  });
});
