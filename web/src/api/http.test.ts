import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiFetch, getAdminToken, setAdminToken } from "./http";

describe("apiFetch", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("{}", { status: 200 })));
  });

  it("attaches X-Admin-Token when token is set", async () => {
    setAdminToken("secret");
    await apiFetch("/admin/knowledge-bases");
    expect(fetch).toHaveBeenCalledWith(
      "/admin/knowledge-bases",
      expect.objectContaining({
        headers: expect.objectContaining({ "X-Admin-Token": "secret" }),
      }),
    );
  });
});

describe("getAdminToken", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("reads token from localStorage", () => {
    setAdminToken("stored");
    expect(getAdminToken()).toBe("stored");
  });
});
