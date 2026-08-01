import { describe, expect, it } from "vitest";
import { queryKeys } from "./query-keys";

describe("query keys", () => {
  it("normalizes search text and includes workspace context", () => {
    expect(
      queryKeys.trackedProfiles.list("workspace-a", {
        active: true,
        q: "  Growth LAB  ",
      }),
    ).toEqual([
      "workspaces",
      "workspace-a",
      "tracked-profiles",
      "list",
      { active: true, q: "growth lab" },
    ]);
  });

  it("does not leak blank filter values into the key", () => {
    expect(queryKeys.trackedProfiles.lists("workspace-b")).toEqual([
      "workspaces",
      "workspace-b",
      "tracked-profiles",
      "list",
    ]);
    expect(
      queryKeys.trackedProfiles.list("workspace-b", { q: "   " }),
    ).toEqual([
      "workspaces",
      "workspace-b",
      "tracked-profiles",
      "list",
      { active: undefined, q: undefined },
    ]);
  });

  it("normalizes inspiration filters without mixing workspaces", () => {
    expect(
      queryKeys.inspirations.list("workspace-c", {
        platform: "douyin",
        status: "candidate",
        q: "  Hook CASE  ",
      }),
    ).toEqual([
      "workspaces",
      "workspace-c",
      "inspirations",
      "list",
      {
        platform: "douyin",
        status: "candidate",
        q: "hook case",
      },
    ]);
  });

  it("keeps P1 discovery, patterns and usage cache scopes separate", () => {
    expect(queryKeys.discovery.search("workspace-p1", "job-1")).toEqual([
      "workspaces",
      "workspace-p1",
      "discovery",
      "search",
      "job-1",
    ]);
    expect(queryKeys.patterns.list("workspace-p1", "validated")).toEqual([
      "workspaces",
      "workspace-p1",
      "patterns",
      "list",
      "validated",
    ]);
    expect(
      queryKeys.usage.provider("workspace-p1", "2026-07-01", "2026-07-30"),
    ).toEqual([
      "workspaces",
      "workspace-p1",
      "usage",
      "provider",
      { dateFrom: "2026-07-01", dateTo: "2026-07-30" },
    ]);
  });

  it("separates automation settings from today's pipeline summary", () => {
    expect(queryKeys.settings.automation("workspace-auto")).toEqual([
      "workspaces",
      "workspace-auto",
      "settings",
      "automation",
    ]);
    expect(queryKeys.production.automationToday("workspace-auto")).toEqual([
      "workspaces",
      "workspace-auto",
      "automation",
      "today",
    ]);
  });
});
