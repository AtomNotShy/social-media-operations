import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

describe("development access-token session", () => {
  beforeEach(() => {
    window.sessionStorage.clear();
    vi.resetModules();
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("uses the documented local-owner identity by default", async () => {
    const { getAccessToken } = await import("./client");

    expect(getAccessToken()).toBe("dev:local-owner");
  });

  it("restores the selected identity after a module reload", async () => {
    const firstClient = await import("./client");
    firstClient.setAccessToken("dev:selected-owner");

    vi.resetModules();
    const reloadedClient = await import("./client");

    expect(reloadedClient.getAccessToken()).toBe("dev:selected-owner");
  });

  it("keeps an explicit logout across a module reload", async () => {
    const firstClient = await import("./client");
    firstClient.setAccessToken(null);

    vi.resetModules();
    const reloadedClient = await import("./client");

    expect(reloadedClient.getAccessToken()).toBeNull();
  });

  it("does not create a development identity in production", async () => {
    vi.stubEnv("NODE_ENV", "production");
    vi.resetModules();

    const productionClient = await import("./client");

    expect(productionClient.getAccessToken()).toBeNull();
  });
});
