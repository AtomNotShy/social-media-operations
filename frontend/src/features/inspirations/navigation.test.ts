import { describe, expect, it } from "vitest";
import { buildInspirationsSearchHref } from "@/src/features/inspirations/navigation";

describe("buildInspirationsSearchHref", () => {
  it("does not rewrite the route when the search query is unchanged", () => {
    expect(
      buildInspirationsSearchHref({
        workspaceId: "workspace-1",
        search: "platform=x&q=creator",
        query: "creator",
      }),
    ).toBeNull();
  });

  it("preserves filters and clears the cursor when the query changes", () => {
    expect(
      buildInspirationsSearchHref({
        workspaceId: "workspace-1",
        search: "platform=x&status=inbox&cursor=next&q=old",
        query: " new idea ",
      }),
    ).toBe(
      "/w/workspace-1/inspirations?platform=x&status=inbox&q=new+idea",
    );
  });

  it("removes an empty query without leaving a trailing question mark", () => {
    expect(
      buildInspirationsSearchHref({
        workspaceId: "workspace-1",
        search: "q=creator",
        query: "   ",
      }),
    ).toBe("/w/workspace-1/inspirations");
  });
});
