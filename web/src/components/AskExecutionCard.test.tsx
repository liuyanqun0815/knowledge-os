import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";
import { AskExecutionCard } from "./AskExecutionCard";

describe("AskExecutionCard", () => {
  afterEach(cleanup);

  it("renders step rows collapsed by default and shows duration", async () => {
    const user = userEvent.setup();
    render(
      <AskExecutionCard
        steps={[
          {
            node: "retrieve",
            status: "ok",
            summary: "命中 3 条",
            duration_ms: 1200,
            detail: { hit_count: 3 },
          },
        ]}
      />,
    );
    expect(screen.getByText(/执行结果/)).toBeInTheDocument();
    expect(screen.getByText(/混合检索|retrieve/)).toBeInTheDocument();
    expect(screen.getByText(/1\.20 秒|1200/)).toBeInTheDocument();
    expect(screen.queryByText("命中 3 条")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /混合检索|retrieve/ }));
    expect(screen.getByText("命中 3 条")).toBeInTheDocument();
  });
});
