export type TrackedProfileFilters = {
  active?: boolean;
  q?: string;
};

export type InspirationFilters = {
  platform?: string;
  status?: string;
  q?: string;
};

export const queryKeys = {
  me: ["me"] as const,
  workspaces: ["workspaces"] as const,
  workspace: (workspaceId: string) =>
    ["workspaces", workspaceId, "detail"] as const,
  trackedProfiles: {
    all: (workspaceId: string) =>
      ["workspaces", workspaceId, "tracked-profiles"] as const,
    list: (workspaceId: string, filters: TrackedProfileFilters) =>
      [
        "workspaces",
        workspaceId,
        "tracked-profiles",
        "list",
        {
          active: filters.active,
          q: filters.q?.trim().toLowerCase() || undefined,
        },
      ] as const,
    detail: (workspaceId: string, profileId: string) =>
      [
        "workspaces",
        workspaceId,
        "tracked-profiles",
        "detail",
        profileId,
      ] as const,
    contents: (workspaceId: string, profileId: string) =>
      [
        "workspaces",
        workspaceId,
        "tracked-profiles",
        "detail",
        profileId,
        "contents",
      ] as const,
  },
  inspirations: {
    all: (workspaceId: string) =>
      ["workspaces", workspaceId, "inspirations"] as const,
    list: (workspaceId: string, filters: InspirationFilters) =>
      [
        "workspaces",
        workspaceId,
        "inspirations",
        "list",
        {
          platform: filters.platform || undefined,
          status: filters.status || undefined,
          q: filters.q?.trim().toLowerCase() || undefined,
        },
      ] as const,
    detail: (workspaceId: string, inspirationId: string) =>
      [
        "workspaces",
        workspaceId,
        "inspirations",
        "detail",
        inspirationId,
      ] as const,
    scores: (workspaceId: string, inspirationId: string) =>
      [
        "workspaces",
        workspaceId,
        "inspirations",
        inspirationId,
        "scores",
      ] as const,
    comments: (workspaceId: string, inspirationId: string) =>
      [
        "workspaces",
        workspaceId,
        "inspirations",
        inspirationId,
        "comments",
      ] as const,
    analyses: (workspaceId: string, inspirationId: string) =>
      [
        "workspaces",
        workspaceId,
        "inspirations",
        inspirationId,
        "analyses",
      ] as const,
    transcripts: (workspaceId: string, inspirationId: string) =>
      [
        "workspaces",
        workspaceId,
        "inspirations",
        inspirationId,
        "transcripts",
      ] as const,
    metrics: (workspaceId: string, inspirationId: string) =>
      [
        "workspaces",
        workspaceId,
        "inspirations",
        inspirationId,
        "metrics",
      ] as const,
  },
  discovery: {
    estimate: (workspaceId: string, maxPages: number) =>
      ["workspaces", workspaceId, "discovery", "estimate", maxPages] as const,
    search: (workspaceId: string, jobId: string) =>
      ["workspaces", workspaceId, "discovery", "search", jobId] as const,
  },
  patterns: {
    all: (workspaceId: string) =>
      ["workspaces", workspaceId, "patterns"] as const,
    list: (workspaceId: string, status?: string) =>
      ["workspaces", workspaceId, "patterns", "list", status || undefined] as const,
    detail: (workspaceId: string, patternId: string) =>
      ["workspaces", workspaceId, "patterns", "detail", patternId] as const,
  },
  usage: {
    provider: (workspaceId: string, dateFrom?: string, dateTo?: string) =>
      [
        "workspaces",
        workspaceId,
        "usage",
        "provider",
        { dateFrom, dateTo },
      ] as const,
    ai: (workspaceId: string, dateFrom?: string, dateTo?: string) =>
      ["workspaces", workspaceId, "usage", "ai", { dateFrom, dateTo }] as const,
    asr: (workspaceId: string, dateFrom?: string, dateTo?: string) =>
      ["workspaces", workspaceId, "usage", "asr", { dateFrom, dateTo }] as const,
  },
  jobs: {
    all: (workspaceId: string) =>
      ["workspaces", workspaceId, "jobs"] as const,
  },
  production: {
    channels: (workspaceId: string) =>
      ["workspaces", workspaceId, "owned-channels"] as const,
    channel: (workspaceId: string, channelId: string) =>
      ["workspaces", workspaceId, "owned-channels", channelId] as const,
    topics: (workspaceId: string, status?: string) =>
      ["workspaces", workspaceId, "topics", status || undefined] as const,
    topic: (workspaceId: string, topicId: string) =>
      ["workspaces", workspaceId, "topics", topicId] as const,
    projects: (workspaceId: string, status?: string) =>
      ["workspaces", workspaceId, "content-projects", status || undefined] as const,
    project: (workspaceId: string, projectId: string) =>
      ["workspaces", workspaceId, "content-projects", projectId] as const,
    scripts: (workspaceId: string, projectId: string) =>
      ["workspaces", workspaceId, "content-projects", projectId, "scripts"] as const,
    assets: (workspaceId: string, projectId?: string) =>
      ["workspaces", workspaceId, "assets", projectId || undefined] as const,
    plans: (workspaceId: string, status?: string) =>
      ["workspaces", workspaceId, "publish-plans", status || undefined] as const,
    reviews: (workspaceId: string, recordId?: string) =>
      ["workspaces", workspaceId, "reviews", recordId || "all"] as const,
    today: (workspaceId: string) =>
      ["workspaces", workspaceId, "dashboard", "today"] as const,
    performance: (workspaceId: string, days: number) =>
      ["workspaces", workspaceId, "dashboard", "performance", days] as const,
    savedViews: (workspaceId: string, entityType: string) =>
      ["workspaces", workspaceId, "saved-views", entityType] as const,
    search: (workspaceId: string, query: string) =>
      ["workspaces", workspaceId, "search", query.trim().toLowerCase()] as const,
    experiments: (workspaceId: string) =>
      ["workspaces", workspaceId, "experiments"] as const,
  },
};
