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
      x: "Twitter",
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

export function jobTypeLabel(type: string) {
  return (
    {
      PROFILE_SCAN: "对标账号同步",
      CONTENT_DETAIL_FETCH: "内容详情采集",
      AI_ANALYSIS: "AI 内容分析",
      TRANSCRIBE: "内容转写",
      CONTENT_GENERATION: "内容生成",
      COMMENT_FETCH: "评论采集",
      DISCOVERY_SEARCH: "内容搜索",
      VIDEO_PRODUCTION: "视频制作",
      CONTENT_IMPORT: "内容导入",
      TRANSCRIPTION: "内容转写",
      ANALYSIS: "AI 内容分析",
    }[type] ?? "其他后台任务"
  );
}

export function jobErrorLabel(code: string | null | undefined) {
  return (
    {
      PROVIDER_ERROR: "数据源请求失败，请稍后重试。",
      PROVIDER_PAYMENT_REQUIRED: "数据源额度或订阅不可用，请检查供应商账户。",
      PROVIDER_BUDGET_EXCEEDED: "工作区数据采集预算已用尽。",
      PROVIDER_RATE_LIMITED: "数据源请求过于频繁，请稍后重试。",
      PROVIDER_AUTH_FAILED: "数据源认证失败，请检查连接配置。",
      PROVIDER_SCHEMA_CHANGED: "数据源响应格式发生变化，需要更新解析规则。",
      PROVIDER_CIRCUIT_OPEN: "数据源暂时不可用，系统将在稍后重试。",
      SOURCE_CONTENT_UNAVAILABLE: "原内容已不可访问或不存在。",
      AI_OUTPUT_TRUNCATED: "AI 输出超出长度限制，未能生成完整结果。",
      AI_OUTPUT_INVALID: "AI 返回结果格式不正确。",
      AI_AUTH_FAILED: "AI 服务认证失败，请检查连接配置。",
      AI_NOT_CONFIGURED: "尚未配置可用于此任务的 AI 服务。",
      AI_PROVIDER_ERROR: "AI 服务请求失败，请稍后重试。",
      ANALYSIS_BUDGET_EXCEEDED: "工作区 AI 分析预算已用尽。",
      INTERNAL_JOB_ERROR: "任务处理过程中发生内部错误。",
      JOB_TYPE_UNSUPPORTED: "当前任务类型暂不受支持。",
    }[code ?? ""] ?? "任务执行失败，请查看后端日志或稍后重试。"
  );
}

export function isTerminalJob(status: string) {
  return ["succeeded", "failed", "dead", "cancelled"].includes(status);
}
