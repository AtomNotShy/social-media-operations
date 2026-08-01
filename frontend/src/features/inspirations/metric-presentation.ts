import type { ContentMetricSnapshot } from "@/src/features/inspirations/types";

export type MetricField =
  | "views"
  | "likes"
  | "comments"
  | "favorites"
  | "shares";

export type MetricPresentationItem = {
  field: MetricField;
  label: string;
  value: number | null;
};

const VIDEO_PLATFORMS = new Set([
  "bilibili",
  "douyin",
  "kuaishou",
  "tiktok",
  "wechat_channels",
  "youtube",
]);

export function metricPresentation(
  platform: string,
  snapshot: ContentMetricSnapshot,
): MetricPresentationItem[] {
  if (platform.toLowerCase() === "x") {
    return [
      { field: "views", label: "浏览", value: snapshot.views },
      { field: "likes", label: "喜欢", value: snapshot.likes },
      { field: "comments", label: "回复", value: snapshot.comments },
      { field: "shares", label: "转推", value: snapshot.shares },
    ];
  }

  return [
    {
      field: "views",
      label: VIDEO_PLATFORMS.has(platform.toLowerCase()) ? "播放" : "浏览",
      value: snapshot.views,
    },
    { field: "likes", label: "点赞", value: snapshot.likes },
    { field: "comments", label: "评论", value: snapshot.comments },
    { field: "favorites", label: "收藏", value: snapshot.favorites },
    { field: "shares", label: "分享", value: snapshot.shares },
  ];
}
