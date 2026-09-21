import { afterEach, describe, expect, it, vi } from "vitest";
import { request, setOnUnauthorized } from "./client.js";

function jsonResponse(status, body, headers = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...headers },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
  setOnUnauthorized(null);
});

describe("api client auth handling", () => {
  it("does not redirect on 401 from /auth/signin", async () => {
    const onUnauthorized = vi.fn();
    setOnUnauthorized(onUnauthorized);
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(401, { error: { type: "invalid_credentials", message: "nope" } })
      )
    );

    const result = await request("/auth/signin", {
      method: "POST",
      json: { email: "a@b.c", password: "x" },
      auth: "none",
    });

    expect(result.ok).toBe(false);
    expect(result.error.type).toBe("invalid_credentials");
    expect(onUnauthorized).not.toHaveBeenCalled();
  });

  it("calls onUnauthorized for 401 on required endpoints", async () => {
    const onUnauthorized = vi.fn();
    setOnUnauthorized(onUnauthorized);
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse(401, { error: { type: "not_authenticated" } }))
    );

    const result = await request("/query", {
      method: "POST",
      json: { session_id: "s", question: "q" },
      auth: "required",
    });

    expect(result.ok).toBe(false);
    expect(onUnauthorized).toHaveBeenCalledTimes(1);
  });

  it("does not redirect on 401 from GET /me when auth is optional", async () => {
    const onUnauthorized = vi.fn();
    setOnUnauthorized(onUnauthorized);
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse(401, { error: { type: "not_authenticated" } }))
    );
    const result = await request("/me", { auth: "optional" });
    expect(result.ok).toBe(false);
    expect(onUnauthorized).not.toHaveBeenCalled();
  });
});
