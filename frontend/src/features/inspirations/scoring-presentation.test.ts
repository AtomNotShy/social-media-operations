import { describe, expect, it } from "vitest";
import {
  scoreConfidenceLabel,
  scoreEvidenceMeta,
  scoreGradeLabel,
  scoreModeLabel,
  scoreReasonLabel,
} from "@/src/features/inspirations/scoring-presentation";

describe("scoring presentation", () => {
  it("translates score outcomes without hiding known tiers", () => {
    expect(scoreGradeLabel("insufficient")).toBe("数据不足");
    expect(scoreGradeLabel("qualified")).toBe("已过门槛");
    expect(scoreGradeLabel("T1")).toBe("T1");
  });

  it("turns baseline reasons into actionable Chinese guidance", () => {
    expect(scoreReasonLabel("baseline_profile_missing")).toContain("未关联作者");
    expect(scoreReasonLabel("insufficient_baseline")).toContain("历史样本不足");
    expect(scoreReasonLabel("minimum_age_not_reached")).toContain("观察期");
    expect(scoreReasonLabel("metric_threshold_not_reached")).toContain("未达到");
    expect(scoreGradeLabel("below_threshold")).toBe("未达门槛");
  });

  it("presents score mode and confidence when supplied", () => {
    expect(scoreModeLabel("content_independent")).toBe("内容独立评分");
    expect(scoreConfidenceLabel("medium")).toBe("中");
    expect(scoreConfidenceLabel(0.86)).toBe("86%");
    expect(
      scoreEvidenceMeta({ score_mode: "author_relative", confidence: "high" }),
    ).toEqual({ mode: "账号相对评分", confidence: "高" });
    expect(scoreEvidenceMeta({ policy_version: 1 }).mode).toBe("账号相对评分");
    expect(
      scoreEvidenceMeta({ automation_gate: { configured: true } }).mode,
    ).toBe("硬门槛评分");
  });
});
