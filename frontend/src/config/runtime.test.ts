import { describe, expect, it } from "vitest";
import { isLocalDevelopmentEnv } from "./runtime";

describe("runtime environment controls", () => {
  it("enables development controls only for the explicit local build", () => {
    expect(isLocalDevelopmentEnv("local")).toBe(true);
    expect(isLocalDevelopmentEnv("development")).toBe(false);
    expect(isLocalDevelopmentEnv("production")).toBe(false);
    expect(isLocalDevelopmentEnv(undefined)).toBe(false);
  });
});
