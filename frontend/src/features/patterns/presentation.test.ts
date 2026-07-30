import { describe, expect, it } from "vitest";
import { evidenceValues, patternStatusLabel } from "./presentation";

describe("pattern presentation", () => {
  it("maps lifecycle states consistently", () => {
    expect(patternStatusLabel("draft")).toBe("草稿");
    expect(patternStatusLabel("validated")).toBe("已验证");
    expect(patternStatusLabel("retired")).toBe("已退役");
  });

  it("does not invent evidence counts", () => {
    expect(evidenceValues({})).toEqual({
      success: 0,
      failure: 0,
      limitations: "尚未记录不适用条件",
    });
    expect(
      evidenceValues({
        success_count: 3,
        failure_count: 1,
        limitations: "不适合纯品牌片",
      }),
    ).toEqual({
      success: 3,
      failure: 1,
      limitations: "不适合纯品牌片",
    });
  });
});
