"use client";

import { ArrowRight, Bot, CircleDot, Radar, Sparkles } from "lucide-react";
import Link from "next/link";
import { ErrorState } from "@/src/components/ui/error-state";
import { StatusBadge } from "@/src/components/ui/status-badge";
import { useAutomationToday } from "@/src/features/automation/queries";
import type { AutomationCandidate } from "@/src/features/automation/types";
import {
  scoreConfidenceLabel,
  scoreGradeLabel,
  scoreModeLabel,
} from "@/src/features/inspirations/scoring-presentation";
import { secondaryButton } from "@/src/features/production/ui";

const platformLabels: Record<string, string> = {
  xiaohongshu: "小红书",
  douyin: "抖音",
  tiktok: "TikTok",
  weibo: "微博",
  youtube: "YouTube",
};

export function AutomationTodayPanel({ workspaceId }: { workspaceId: string }) {
  const automation = useAutomationToday(workspaceId);

  if (automation.isLoading) {
    return <div className="mb-5 h-72 animate-pulse rounded-xl bg-surface" />;
  }
  if (automation.error || !automation.data) {
    return (
      <section className="mb-5 rounded-xl border border-border bg-surface shadow-panel">
        <ErrorState
          message="今日自动化流水线暂时无法读取。"
          onRetry={() => automation.refetch()}
          requestId={(automation.error as { requestId?: string })?.requestId}
        />
      </section>
    );
  }

  const data = automation.data;
  return (
    <section className="mb-5 rounded-xl border border-border bg-surface shadow-panel">
      <div className="flex flex-col gap-3 border-b border-border p-5 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex items-start gap-3">
          <span className="rounded-lg bg-primary-50 p-2 text-primary-600">
            <Radar aria-hidden="true" size={18} />
          </span>
          <div>
            <h2 className="font-semibold">今日自动发现</h2>
            <p className="mt-1 text-xs leading-5 text-text-muted">
              规则先筛选，只有通过硬门槛的内容才会进入 AI 分析。
            </p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2 text-xs text-text-muted">
          {data.actual_cost_usd != null ? (
            <span>今日实际 AI 成本 ${formatCost(data.actual_cost_usd)}</span>
          ) : data.estimated_cost_usd != null ? (
            <span>预计 AI 成本 ${formatCost(data.estimated_cost_usd)}</span>
          ) : null}
          <Link className={secondaryButton} href={`/w/${workspaceId}/settings`}>
            调整规则
          </Link>
        </div>
      </div>

      <div className="p-5">
        <div className="grid grid-cols-2 gap-2 lg:grid-cols-4 xl:grid-cols-8">
          <FunnelStat label="扫描账号" value={data.scanned_profiles} />
          <FunnelStat label="发现内容" value={data.discovered_contents} />
          <FunnelStat label="观察中" tone="warning" value={data.observing_contents} />
          <FunnelStat label="通过门槛" tone="success" value={data.qualified_contents} />
          <FunnelStat label="L1 排队" value={data.l1_queued} />
          <FunnelStat label="L1 完成" tone="success" value={data.l1_completed} />
          <FunnelStat label="L2 排队" value={data.l2_queued} />
          <FunnelStat label="L2 完成" tone="success" value={data.l2_completed} />
        </div>

        <div className="mt-5 flex items-center justify-between gap-3">
          <h3 className="flex items-center gap-2 text-sm font-semibold">
            <Sparkles className="text-primary-600" size={16} /> 今日精选候选
          </h3>
          <Link
            className="text-xs font-medium text-primary-600 hover:underline"
            href={`/w/${workspaceId}/inspirations`}
          >
            查看全部灵感
          </Link>
        </div>
        {data.candidates.length ? (
          <div className="mt-3 grid gap-2 lg:grid-cols-2">
            {data.candidates.slice(0, 6).map((candidate) => (
              <CandidateRow
                candidate={candidate}
                key={candidate.inspiration_id}
                workspaceId={workspaceId}
              />
            ))}
          </div>
        ) : (
          <p className="mt-3 rounded-lg bg-surface-subtle p-4 text-sm text-text-muted">
            今天还没有通过门槛的候选内容。观察池会按规则继续刷新，不会调用 AI。
          </p>
        )}
      </div>
    </section>
  );
}

function FunnelStat({
  label,
  value,
  tone = "neutral",
}: {
  label: string;
  value: number;
  tone?: "neutral" | "warning" | "success";
}) {
  const toneClass = {
    neutral: "bg-surface-subtle text-text",
    warning: "bg-warning/10 text-warning",
    success: "bg-success/10 text-success",
  }[tone];
  return (
    <div className={`rounded-lg p-3 ${toneClass}`}>
      <strong className="block text-xl tabular-nums">{value}</strong>
      <span className="mt-1 block text-[11px] opacity-75">{label}</span>
    </div>
  );
}

function CandidateRow({
  candidate,
  workspaceId,
}: {
  candidate: AutomationCandidate;
  workspaceId: string;
}) {
  const mode = scoreModeLabel(candidate.score_mode);
  const confidence = scoreConfidenceLabel(candidate.confidence);
  const opportunityScore =
    candidate.opportunity_score ?? candidate.content_potential_score;
  const analysis = analysisSummary(candidate);
  return (
    <Link
      className="group flex min-w-0 items-center gap-3 rounded-lg border border-border p-3 transition-colors hover:bg-surface-subtle"
      href={`/w/${workspaceId}/inspirations/${candidate.inspiration_id}`}
    >
      <span className="rounded-lg bg-primary-50 p-2 text-primary-600">
        <Bot size={15} />
      </span>
      <div className="min-w-0 flex-1">
        <strong className="block truncate text-sm">
          {candidate.title?.trim() || "未命名候选内容"}
        </strong>
        <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px] text-text-muted">
          {candidate.platform ? (
            <span>{platformLabels[candidate.platform] ?? candidate.platform}</span>
          ) : null}
          {mode ? <span>{mode}</span> : null}
          {confidence ? <span>置信度 {confidence}</span> : null}
          {opportunityScore != null ? (
            <span className="font-medium text-primary-600">
              机会分 {formatOpportunityScore(opportunityScore)}
            </span>
          ) : null}
          <span className="flex items-center gap-1">
            <CircleDot size={10} /> {analysis}
          </span>
        </div>
      </div>
      {candidate.grade ? (
        <StatusBadge
          label={scoreGradeLabel(candidate.grade)}
          status={candidate.grade}
        />
      ) : null}
      <ArrowRight className="text-text-muted group-hover:text-primary-600" size={15} />
    </Link>
  );
}

function analysisSummary(candidate: AutomationCandidate): string {
  if (candidate.l2_status === "succeeded") return "L2 已完成";
  if (candidate.l2_status === "queued" || candidate.l2_status === "running") {
    return "L2 处理中";
  }
  if (candidate.l1_status === "succeeded") return "L1 已完成";
  if (candidate.l1_status === "queued" || candidate.l1_status === "running") {
    return "L1 处理中";
  }
  return "等待分析";
}

function formatCost(value: string | number): string {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed.toFixed(2) : String(value);
}

function formatOpportunityScore(value: number): string {
  return new Intl.NumberFormat("zh-CN", {
    maximumFractionDigits: 1,
  }).format(value <= 1 ? value * 100 : value);
}
