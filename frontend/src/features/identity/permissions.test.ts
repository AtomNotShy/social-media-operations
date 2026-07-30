import { describe, expect, it } from "vitest";
import { canEditWorkspace, canManageWorkspace } from "./permissions";

describe("workspace permissions", () => {
  it("allows owners and editors to change business data", () => {
    expect(canEditWorkspace("owner")).toBe(true);
    expect(canEditWorkspace("editor")).toBe(true);
  });

  it("keeps viewers and unresolved identities read-only", () => {
    expect(canEditWorkspace("viewer")).toBe(false);
    expect(canEditWorkspace(undefined)).toBe(false);
  });

  it("reserves workspace management for owners", () => {
    expect(canManageWorkspace("owner")).toBe(true);
    expect(canManageWorkspace("editor")).toBe(false);
  });
});
