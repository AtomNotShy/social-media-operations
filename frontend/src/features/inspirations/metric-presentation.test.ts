import { describe, expect, it } from "vitest";
import type { ContentMetricSnapshot } from "@/src/features/inspirations/types";
import { metricPresentation } from "./metric-presentation";

const snapshot: ContentMetricSnapshot = {
  id: "snapshot-1",
  external_content_id: "content-1",
  captured_at: "2026-08-01T08:00:00.000Z",
  views: 12_800,
  likes: 4_286,
  comments: 318,
  favorites: 1_204,
  shares: 562,
  downloads: null,
  metrics: {},
};

describe("metricPresentation", () => {
  it("uses X-specific terminology and omits favorites", () => {
    expect(metricPresentation("x", snapshot)).toEqual([
      { field: "views", label: "浏览", value: 12_800 },
      { field: "likes", label: "喜欢", value: 4_286 },
      { field: "comments", label: "回复", value: 318 },
      { field: "shares", label: "转推", value: 562 },
    ]);
  });

  it("uses playback terminology for video-first platforms", () => {
    expect(metricPresentation("douyin", snapshot).map((item) => item.label)).toEqual([
      "播放",
      "点赞",
      "评论",
      "收藏",
      "分享",
    ]);
    expect(metricPresentation("bilibili", snapshot)[0].label).toBe("播放");
  });

  it("uses browsing terminology and all supported fields for Xiaohongshu", () => {
    expect(
      metricPresentation("xiaohongshu", snapshot).map((item) => item.label),
    ).toEqual(["浏览", "点赞", "评论", "收藏", "分享"]);
  });
});
