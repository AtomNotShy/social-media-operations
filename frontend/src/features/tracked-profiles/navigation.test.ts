import { describe, expect, it } from "vitest";
import { buildTrackedProfilesSearchHref } from "@/src/features/tracked-profiles/navigation";

describe("buildTrackedProfilesSearchHref", () => {
  it("does not rewrite the current route when the query is unchanged", () => {
    expect(
      buildTrackedProfilesSearchHref({
        workspaceId: "workspace-1",
        search: "active=true&q=creator",
        query: "creator",
      }),
    ).toBeNull();
  });

  it("updates the query and clears a stale cursor", () => {
    expect(
      buildTrackedProfilesSearchHref({
        workspaceId: "workspace-1",
        search: "active=true&cursor=next-page&q=old",
        query: " new creator ",
      }),
    ).toBe(
      "/w/workspace-1/tracked-profiles?active=true&q=new+creator",
    );
  });

  it("removes an empty query without leaving a trailing question mark", () => {
    expect(
      buildTrackedProfilesSearchHref({
        workspaceId: "workspace-1",
        search: "q=creator",
        query: "   ",
      }),
    ).toBe("/w/workspace-1/tracked-profiles");
  });
});
