import { describe, expect, it } from "vitest";
import {
  authorName,
  contentTitle,
  detailStatusLabel,
  formatMetric,
  inspirationStatusLabel,
} from "./presentation";

describe("inspiration presentation", () => {
  it("uses stable Chinese labels for workflow states", () => {
    expect(inspirationStatusLabel("candidate")).toBe("候选选题");
    expect(detailStatusLabel("ready")).toBe("详情就绪");
  });

  it("falls back from title to body without inventing content", () => {
    expect(contentTitle(null, "  一段可以作为标题的正文内容  ")).toBe(
      "一段可以作为标题的正文内容",
    );
    expect(contentTitle(null, null)).toBe("未命名内容");
  });

  it("reads common author snapshot fields", () => {
    expect(authorName({ nickname: "运营研究所" })).toBe("运营研究所");
    expect(authorName({ follower_count: 100 })).toBe("公开内容");
  });

  it("distinguishes missing metrics from a real zero", () => {
    expect(formatMetric(null)).toBe("—");
    expect(formatMetric(0)).toBe("0");
    expect(formatMetric(12800)).toBe("12,800");
  });
});
