export type ThresholdMatch = "any" | "all";

export type AutomationMetricThresholds = {
  views: number;
  likes: number;
  comments: number;
  favorites: number;
  shares: number;
};

export type AutomationSettings = {
  enabled: boolean;
  scan_interval_hours: number;
  observation_hours: number;
  minimum_age_minutes: number;
  metric_thresholds: AutomationMetricThresholds;
  threshold_match: ThresholdMatch;
  auto_l1: boolean;
  auto_l2: boolean;
  daily_l1_limit: number;
  daily_l2_limit: number;
};

export type AutomationCandidate = {
  inspiration_id: string;
  title: string | null;
  platform?: string | null;
  grade?: string | null;
  opportunity_score?: number | null;
  content_potential_score?: number | null;
  score_mode?: string | null;
  confidence?: string | number | null;
  l1_status?: string | null;
  l2_status?: string | null;
  qualified_at?: string | null;
};

export type AutomationToday = {
  timezone: string;
  window_start: string;
  window_end: string;
  scanned_profiles: number;
  discovered_contents: number;
  observing_contents: number;
  qualified_contents: number;
  l1_queued: number;
  l1_completed: number;
  l2_queued: number;
  l2_completed: number;
  estimated_cost_usd?: string | number | null;
  actual_cost_usd?: string | number | null;
  candidates: AutomationCandidate[];
};

export const demoAutomationSettings: AutomationSettings = {
  enabled: true,
  scan_interval_hours: 24,
  observation_hours: 72,
  minimum_age_minutes: 120,
  metric_thresholds: {
    views: 10_000,
    likes: 200,
    comments: 30,
    favorites: 100,
    shares: 50,
  },
  threshold_match: "any",
  auto_l1: true,
  auto_l2: true,
  daily_l1_limit: 20,
  daily_l2_limit: 5,
};

export const demoAutomationToday: AutomationToday = {
  timezone: "Australia/Melbourne",
  window_start: new Date().toISOString().slice(0, 10),
  window_end: new Date(Date.now() + 86_400_000).toISOString(),
  scanned_profiles: 20,
  discovered_contents: 86,
  observing_contents: 18,
  qualified_contents: 9,
  l1_queued: 0,
  l1_completed: 9,
  l2_queued: 1,
  l2_completed: 4,
  estimated_cost_usd: "1.26",
  actual_cost_usd: "1.08",
  candidates: [
    {
      inspiration_id: "demo-inspiration-001",
      title: "一个被忽略的增长信号：收藏比点赞更早出现",
      platform: "xiaohongshu",
      grade: "T1",
      opportunity_score: 86,
      score_mode: "author_relative",
      confidence: "high",
      l1_status: "succeeded",
      l2_status: "succeeded",
    },
  ],
};
