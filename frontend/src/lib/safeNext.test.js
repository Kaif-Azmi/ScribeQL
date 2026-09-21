import { describe, expect, it } from "vitest";
import { safeNext } from "../lib/safeNext.js";

describe("safeNext", () => {
  it("accepts a same-origin path", () => {
    expect(safeNext("/start")).toBe("/start");
    expect(safeNext("/account?reauth=1")).toBe("/account?reauth=1");
    expect(safeNext("/studio/demo")).toBe("/studio/demo");
  });

  it("rejects open redirects", () => {
    expect(safeNext("//evil.example")).toBe("/start");
    expect(safeNext("/\\evil")).toBe("/start");
    expect(safeNext("https://evil.example")).toBe("/start");
    expect(safeNext("http://evil.example/x")).toBe("/start");
    expect(safeNext("start")).toBe("/start");
    expect(safeNext("")).toBe("/start");
    expect(safeNext(null)).toBe("/start");
  });
});
