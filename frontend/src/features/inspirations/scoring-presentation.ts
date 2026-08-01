const gradeLabels: Record<string, string> = {
  insufficient: "数据不足",
  qualified: "已过门槛",
  ordinary: "普通",
  low_quality: "低表现",
  below_threshold: "未达门槛",
};

const reasonLabels: Record<string, string> = {
  baseline_profile_missing: "未关联作者，无法计算账号相对基线",
  insufficient_baseline: "作者历史样本不足，暂无法计算账号相对基线",
  follower_snapshot_missing: "缺少作者粉丝快照",
  required_metrics_missing: "缺少评分所需的公开指标",
  minimum_age_not_reached: "发布时间较短，仍在最短观察期内",
  candidate_metrics_missing: "当前内容缺少可用的公开指标",
  published_at_missing: "缺少发布时间，无法判断观察窗口",
  metric_threshold_not_reached: "公开指标尚未达到硬门槛",
  observation_window_expired: "观察窗口已结束，内容未达到硬门槛",
  thresholds_not_configured: "尚未配置有效的公开指标门槛",
};

const modeLabels: Record<string, string> = {
  author_relative: "账号相对评分",
  platform_relative: "平台对照评分",
  content_independent: "内容独立评分",
  hard_threshold: "硬门槛评分",
  insufficient: "证据不足",
};

const confidenceLabels: Record<string, string> = {
  high: "高",
  medium: "中",
  low: "低",
};

export function scoreGradeLabel(grade?: string | null): string {
  if (!grade) return "—";
  return gradeLabels[grade.toLowerCase()] ?? grade;
}

export function scoreReasonLabel(reason: unknown): string {
  const value = String(reason);
  return reasonLabels[value] ?? value;
}

export function scoreModeLabel(mode?: unknown): string | null {
  if (typeof mode !== "string" || !mode) return null;
  return modeLabels[mode] ?? mode;
}

export function scoreConfidenceLabel(confidence?: unknown): string | null {
  if (typeof confidence === "number" && Number.isFinite(confidence)) {
    const percent = confidence <= 1 ? confidence * 100 : confidence;
    return `${Math.round(percent)}%`;
  }
  if (typeof confidence !== "string" || !confidence) return null;
  return confidenceLabels[confidence.toLowerCase()] ?? confidence;
}

export function scoreEvidenceMeta(evidence: Record<string, unknown>): {
  mode: string | null;
  confidence: string | null;
} {
  const automationGate = evidence.automation_gate;
  const gateConfigured =
    typeof automationGate === "object" &&
    automationGate !== null &&
    (automationGate as Record<string, unknown>).configured === true;
  const inferredMode = gateConfigured
    ? "hard_threshold"
    : evidence.policy_version != null
      ? "author_relative"
      : null;
  return {
    mode: scoreModeLabel(evidence.score_mode ?? evidence.mode ?? inferredMode),
    confidence: scoreConfidenceLabel(evidence.confidence),
  };
}
