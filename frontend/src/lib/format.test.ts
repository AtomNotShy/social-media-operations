import { describe, expect, it } from "vitest";
import {
  formatCompactNumber,
  isTerminalJob,
  jobStatusLabel,
  platformLabel,
} from "./format";

describe("format helpers", () => {
  it("keeps missing metrics distinct from zero", () => {
    expect(formatCompactNumber(null)).toBe("—");
    expect(formatCompactNumber(0)).toBe("0");
  });

  it("maps platform and job language for users", () => {
    expect(platformLabel("xiaohongshu")).toBe("小红书");
    expect(jobStatusLabel("retry_wait")).toBe("等待重试");
  });

  it("stops polling only for terminal jobs", () => {
    expect(isTerminalJob("running")).toBe(false);
    expect(isTerminalJob("failed")).toBe(true);
    expect(isTerminalJob("cancelled")).toBe(true);
  });
});
