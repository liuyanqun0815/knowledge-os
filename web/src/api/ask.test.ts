import { beforeEach, describe, expect, it, vi } from "vitest";

describe("askQuestion", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.resetModules();
  });

  it("posts knowledge_base_id and question", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            text: "ok",
            claim_ids: [],
            evidence: [],
            confidence: 0.5,
            retrieval_mode: "hybrid",
            request_id: null,
            trace: null,
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      ),
    );
    const { askQuestion } = await import("./ask");
    await askQuestion({ knowledgeBaseId: "kb-1", question: "q" });
    expect(fetch).toHaveBeenCalledWith(
      "/ask",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ knowledge_base_id: "kb-1", question: "q" }),
      }),
    );
  });

  it("fetches trace by knowledge base and request id", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ trace: [{ node: "retrieve", status: "ok" }] }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );
    const { fetchTrace } = await import("./ask");
    const steps = await fetchTrace("kb-1", "req-42");
    expect(fetch).toHaveBeenCalledWith("/admin/knowledge-bases/kb-1/traces/req-42", expect.any(Object));
    expect(steps).toEqual([{ node: "retrieve", status: "ok" }]);
  });

  it("returns empty trace when response omits trace field", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({}), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );
    const { fetchTrace } = await import("./ask");
    await expect(fetchTrace("kb-1", "req-42")).resolves.toEqual([]);
  });
});
