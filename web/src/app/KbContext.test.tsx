import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";
import { KbProvider, useKb } from "./KbContext";

function Probe() {
  const { kbId } = useKb();
  return <span data-testid="kb">{kbId ?? "none"}</span>;
}

describe("KbProvider", () => {
  afterEach(() => {
    localStorage.clear();
  });

  it("prefers ?kb= over localStorage", () => {
    localStorage.setItem("akos_current_kb", "from-storage");

    render(
      <MemoryRouter
        initialEntries={["/ask?kb=from-url"]}
        future={{ v7_relativeSplatPath: true, v7_startTransition: true }}
      >
        <KbProvider>
          <Routes>
            <Route path="/ask" element={<Probe />} />
          </Routes>
        </KbProvider>
      </MemoryRouter>,
    );

    expect(screen.getByTestId("kb")).toHaveTextContent("from-url");
    expect(localStorage.getItem("akos_current_kb")).toBe("from-url");
  });
});
