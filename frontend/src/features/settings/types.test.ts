import { describe, expect, it } from "vitest";
import { demoWorkspace } from "./fixtures";
import { externalCallsState } from "./types";

describe("settings presentation", () => {
  it("reads the external-call emergency state from workspace settings", () => {
    expect(externalCallsState(demoWorkspace)).toEqual({
      paused: false,
      reason: null,
      changedAt: "2026-07-31T01:30:00Z",
    });
  });

  it("defaults safely when an older workspace has no emergency state", () => {
    expect(
      externalCallsState({ ...demoWorkspace, settings: {} }),
    ).toEqual({
      paused: false,
      reason: null,
      changedAt: null,
    });
  });
});
