import { describe, expect, it } from "vitest";
import {
  authorName,
  contentCoverUrl,
  contentTitle,
  detailStatusLabel,
  formatMetric,
  inspirationStatusLabel,
} from "./presentation";

describe("inspiration presentation", () => {
  it("uses stable Chinese labels for workflow states", () => {
    expect(inspirationStatusLabel("candidate")).toBe("候选选题");
    expect(detailStatusLabel("detail")).toBe("详情就绪");
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

  it("prefers a cover and falls back to image media", () => {
    expect(
      contentCoverUrl([
        { type: "image", url: "https://example.com/image.jpg" },
        { type: "cover", url: "https://example.com/cover.jpg" },
      ]),
    ).toBe("https://example.com/cover.jpg");
    expect(
      contentCoverUrl([{ type: "photo", url: "https://example.com/photo.jpg" }]),
    ).toBe("https://example.com/photo.jpg");
    expect(contentCoverUrl([{ type: "video", url: "https://example.com/video.mp4" }])).toBeNull();
  });

  it("distinguishes missing metrics from a real zero", () => {
    expect(formatMetric(null)).toBe("—");
    expect(formatMetric(0)).toBe("0");
    expect(formatMetric(12800)).toBe("12,800");
  });
});
