import { describe, expect, it } from "vitest";
import { AUTH_COPY } from "./errors.js";

describe("auth error mapping", () => {
  it("does not distinguish which sign-in field was wrong", () => {
    expect(AUTH_COPY.invalid_credentials).toBe("Invalid email or password.");
  });

  it("keeps Google failures generic", () => {
    expect(AUTH_COPY.google_failed).not.toMatch(/oauth|token|scope/i);
  });
});
