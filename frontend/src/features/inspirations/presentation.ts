export function inspirationStatusLabel(status: string) {
  return (
    {
      inbox: "待处理",
      analyzed: "已分析",
      candidate: "候选选题",
      archived: "已归档",
    }[status] ?? status
  );
}

export function detailStatusLabel(status: string) {
  return (
    {
      pending: "等待详情",
      summary: "摘要就绪",
      detail: "详情就绪",
      ready: "详情就绪",
      failed: "详情失败",
    }[status] ?? status
  );
}

export function inspirationSourceLabel(source: string) {
  return (
    {
      manual_url: "手动导入",
      tracked_profile: "账号追踪",
      profile_scan: "账号追踪",
      discovery_search: "内容发现",
      workspace_metric_snapshot: "指标快照",
      test: "测试数据",
    }[source] ?? "工作区收录"
  );
}

export function contentTitle(
  title: string | null,
  body: string | null,
  fallback = "未命名内容",
) {
  return title?.trim() || body?.trim().slice(0, 52) || fallback;
}

export function authorName(author: Record<string, unknown>) {
  for (const key of ["display_name", "nickname", "name", "handle"]) {
    const value = author[key];
    if (typeof value === "string" && value.trim()) return value;
  }
  return "公开内容";
}

export function contentCoverUrl(mediaManifest: unknown[]) {
  const media = mediaManifest.filter(
    (item): item is { type?: unknown; url?: unknown } =>
      typeof item === "object" && item !== null,
  );
  const preferredTypes = ["cover", "photo", "image"];

  for (const type of preferredTypes) {
    const match = media.find(
      (item) => item.type === type && typeof item.url === "string" && item.url,
    );
    if (match && typeof match.url === "string") return match.url;
  }

  return null;
}

export function formatMetric(value: number | null | undefined) {
  return value == null ? "—" : new Intl.NumberFormat("zh-CN").format(value);
}

export function scoreGradeBadge(grade: string | null | undefined) {
  return grade === "t1" ? "T1" : grade === "t2" ? "T2" : null;
}

export function formatScoreRatio(value: string | number | null | undefined) {
  if (value == null) return null;
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return null;
  return `R ${new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 2 }).format(parsed)}×`;
}

export function engagementTotal(
  metrics:
    | {
        likes: number | null;
        comments: number | null;
        favorites: number | null;
        shares: number | null;
      }
    | null
    | undefined,
) {
  if (!metrics) return null;
  const values = [
    metrics.likes,
    metrics.comments,
    metrics.favorites,
    metrics.shares,
  ].filter((value): value is number => value != null);
  return values.length ? values.reduce((total, value) => total + value, 0) : null;
}
