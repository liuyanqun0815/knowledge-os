import { beforeEach, describe, expect, it, vi } from "vitest";

const sampleClaim = {
  id: "claim-1",
  family_id: "family-1",
  version: 1,
  subject: "Product A",
  predicate: "has_price",
  object: "99",
  status: "active",
  valid_from: null,
  valid_to: null,
  source_ids: ["src-1"],
  subject_type: "product",
  object_type: "literal",
  confidence: 0.9,
};

describe("listClaims", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.resetModules();
  });

  it("fetches claims without filters", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify([sampleClaim]), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );
    const { listClaims } = await import("./claims");
    const claims = await listClaims("kb-1");
    expect(fetch).toHaveBeenCalledWith("/admin/knowledge-bases/kb-1/claims", expect.any(Object));
    expect(claims).toEqual([sampleClaim]);
  });

  it("passes status and SPO fuzzy query params", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify([]), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );
    const { listClaims } = await import("./claims");
    await listClaims("kb-1", {
      status: "active",
      subject: "Product",
      predicate: "price",
      object: "99",
    });
    expect(fetch).toHaveBeenCalledWith(
      "/admin/knowledge-bases/kb-1/claims?status=active&subject=Product&predicate=price&object=99",
      expect.any(Object),
    );
  });
});

describe("fetchClaimHistory", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.resetModules();
  });

  it("fetches claim history by family id", async () => {
    const historyItem = {
      id: "claim-1",
      family_id: "family-1",
      version: 1,
      subject: "Product A",
      predicate: "has_price",
      object: "99",
      status: "active",
      valid_from: null,
      valid_to: null,
      source_ids: ["src-1"],
    };
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify([historyItem]), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );
    const { fetchClaimHistory } = await import("./claims");
    const history = await fetchClaimHistory("kb-1", "family-1");
    expect(fetch).toHaveBeenCalledWith(
      "/admin/knowledge-bases/kb-1/claims/family-1/history",
      expect.any(Object),
    );
    expect(history).toEqual([historyItem]);
  });
});

describe("staging review api", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.resetModules();
  });

  it("approveStagingClaim posts to approve-staging", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ ...sampleClaim, status: "active" }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );
    const { approveStagingClaim } = await import("./claims");
    await approveStagingClaim("kb-1", "claim-staging");
    expect(fetch).toHaveBeenCalledWith(
      "/admin/knowledge-bases/kb-1/claims/claim-staging/approve-staging",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("rejectStagingClaim posts to reject-staging", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ claim: { ...sampleClaim, status: "superseded" } }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );
    const { rejectStagingClaim } = await import("./claims");
    await rejectStagingClaim("kb-1", "claim-staging");
    expect(fetch).toHaveBeenCalledWith(
      "/admin/knowledge-bases/kb-1/claims/claim-staging/reject-staging",
      expect.objectContaining({ method: "POST" }),
    );
  });
});
