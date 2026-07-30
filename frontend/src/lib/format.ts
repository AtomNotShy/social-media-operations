export function formatCompactNumber(value: number | null | undefined) {
  if (value == null) return "—";
  return new Intl.NumberFormat("zh-CN", {
    notation: value >= 10_000 ? "compact" : "standard",
    maximumFractionDigits: 1,
  }).format(value);
}

export function formatRelativeTime(value: string | null | undefined) {
  if (!value) return "尚未同步";
  const diff = Date.now() - new Date(value).getTime();
  const minutes = Math.max(0, Math.floor(diff / 60_000));
  if (minutes < 1) return "刚刚";
  if (minutes < 60) return `${minutes} 分钟前`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} 小时前`;
  return `${Math.floor(hours / 24)} 天前`;
}

export function platformLabel(platform: string) {
  return (
    {
      douyin: "抖音",
      xiaohongshu: "小红书",
      youtube: "YouTube",
      bilibili: "哔哩哔哩",
      kuaishou: "快手",
      weibo: "微博",
      wechat_channels: "视频号",
      tiktok: "TikTok",
      instagram: "Instagram",
      x: "X",
    }[platform] ?? platform
  );
}

export function jobStatusLabel(status: string) {
  return (
    {
      pending: "等待中",
      running: "执行中",
      retry_wait: "等待重试",
      succeeded: "已完成",
      failed: "失败",
      dead: "需要处理",
      cancelled: "已取消",
    }[status] ?? status
  );
}

export function isTerminalJob(status: string) {
  return ["succeeded", "failed", "dead", "cancelled"].includes(status);
}
