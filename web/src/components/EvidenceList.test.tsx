import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";
import { EvidenceList } from "./EvidenceList";

describe("EvidenceList", () => {
  afterEach(cleanup);

  it("shows an empty evidence message", () => {
    render(<EvidenceList evidence={[]} />);

    expect(screen.getByText("无证据")).toBeInTheDocument();
  });

  it("renders span text and expands the full evidence JSON", async () => {
    const user = userEvent.setup();
    render(<EvidenceList evidence={[{ claim_id: "c1", span: "适用条款", score: 0.92 }]} />);

    expect(screen.getByText("适用条款")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /证据 1/ }));
    expect(screen.getByText(/"claim_id": "c1"/)).toBeInTheDocument();
  });

  it("falls back to quote when span is missing", () => {
    render(<EvidenceList evidence={[{ claim_id: "c2", quote: "生产侧引用原文" }]} />);

    expect(screen.getByText("生产侧引用原文")).toBeInTheDocument();
  });
});
