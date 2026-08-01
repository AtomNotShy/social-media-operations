"use client";

import {
  ArrowLeft,
  BarChart3,
  Check,
  Eye,
  FileText,
  MousePointerClick,
  RefreshCw,
  Save,
  Settings2,
  Sparkles,
  Target,
} from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { ErrorState } from "@/src/components/ui/error-state";
import {
  ContentPerformanceTable,
  formatRate,
  InsightList,
  nativeMetric,
  PerformanceTrendChart,
  PlatformMark,
  summarizePerformance,
} from "@/src/features/production/channel-analytics";
import { useWorkspaceRole } from "@/src/features/identity/queries";
import {
  useChannel,
  usePerformance,
  useSavePositioning,
} from "@/src/features/production/queries";
import type {
  OwnedChannel,
  PerformanceDashboard,
  PositioningUpdate,
} from "@/src/features/production/types";
import {
  InlineError,
  inputClass,
  primaryButton,
  secondaryButton,
  textareaClass,
} from "@/src/features/production/ui";
import { formatCompactNumber, formatRelativeTime, platformLabel } from "@/src/lib/format";

type Tab = "overview" | "content" | "positioning";
type Period = 7 | 30 | 90;

const tabs: { value: Tab; label: string; icon: typeof BarChart3 }[] = [
  { value: "overview", label: "数据概览", icon: BarChart3 },
  { value: "content", label: "内容分析", icon: FileText },
  { value: "positioning", label: "账号定位", icon: Settings2 },
];

export function ChannelDetailPage({
  workspaceId,
  channelId,
}: {
  workspaceId: string;
  channelId: string;
}) {
  const [tab, setTab] = useState<Tab>("overview");
  const [period, setPeriod] = useState<Period>(30);
  const channel = useChannel(workspaceId, channelId);
  const performance = usePerformance(workspaceId, period);
  const permission = useWorkspaceRole(workspaceId);

  if (channel.isLoading) {
    return <div aria-label="正在加载账号分析" className="h-[560px] animate-pulse rounded-xl bg-surface" />;
  }
  if (channel.error || !channel.data) {
    return <ErrorState message="账号详情加载失败。" onRetry={() => channel.refetch()} />;
  }

  const records = (performance.data?.records ?? []).filter(
    (record) => record.owned_channel_id === channelId,
  );
  const summary = summarizePerformance(records);
  const refreshing = channel.isFetching || performance.isFetching;

  return (
    <>
      <Link className="mb-4 inline-flex items-center gap-2 text-xs font-medium text-text-muted hover:text-text" href={`/w/${workspaceId}/channels`}>
        <ArrowLeft size={14} /> 返回自有账号
      </Link>
      <header className="flex flex-col gap-5 border-b border-border pb-5 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex min-w-0 items-center gap-4">
          <PlatformMark platform={channel.data.platform} size="lg" />
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="truncate text-2xl font-semibold tracking-tight">{channel.data.display_name}</h1>
              <span className="inline-flex items-center gap-1.5 text-[11px] font-medium text-success"><i className="size-1.5 rounded-full bg-success" />{channel.data.active ? "账号运行中" : "账号已停用"}</span>
            </div>
            <p className="mt-1.5 text-xs text-text-muted">
              {channel.data.handle || "未设置 handle"} · {platformLabel(channel.data.platform)} · 数据源：已登记发布复盘
            </p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button
            className={secondaryButton}
            disabled={refreshing}
            onClick={() => Promise.all([channel.refetch(), performance.refetch()])}
            type="button"
          >
            <RefreshCw className={refreshing ? "animate-spin" : ""} size={15} />
            {refreshing ? "正在刷新" : "刷新数据"}
          </button>
          <div aria-label="分析时间范围" className="flex rounded-lg border border-border bg-surface p-1">
            {([7, 30, 90] as Period[]).map((value) => (
              <button
                aria-pressed={period === value}
                className={`rounded-md px-3 py-1.5 text-xs font-medium transition ${period === value ? "bg-primary-600 text-white shadow-sm" : "text-text-muted hover:text-text"}`}
                key={value}
                onClick={() => setPeriod(value)}
                type="button"
              >
                {value} 天
              </button>
            ))}
          </div>
        </div>
      </header>

      <nav aria-label="账号详情视图" className="flex gap-6 overflow-x-auto border-b border-border" role="tablist">
        {tabs.map((item) => (
          <button
            aria-selected={tab === item.value}
            className={`relative flex shrink-0 items-center gap-2 px-1 py-4 text-sm font-medium transition ${tab === item.value ? "text-primary-700 after:absolute after:inset-x-0 after:bottom-0 after:h-0.5 after:bg-primary-600" : "text-text-muted hover:text-text"}`}
            key={item.value}
            onClick={() => setTab(item.value)}
            role="tab"
            type="button"
          >
            <item.icon size={15} />{item.label}
          </button>
        ))}
      </nav>

      {performance.error && tab !== "positioning" ? (
        <div className="mt-5"><ErrorState message="账号表现数据加载失败。" onRetry={() => performance.refetch()} /></div>
      ) : tab === "overview" ? (
        <OverviewTab channel={channel.data} loading={performance.isLoading} period={period} records={records} summary={summary} workspaceId={workspaceId} />
      ) : tab === "content" ? (
        <ContentTab channel={channel.data} loading={performance.isLoading} records={records} summary={summary} workspaceId={workspaceId} />
      ) : (
        <PositioningTab canEdit={permission.canEdit} channel={channel.data} workspaceId={workspaceId} />
      )}
    </>
  );
}

function OverviewTab({
  channel,
  records,
  summary,
  period,
  loading,
  workspaceId,
}: {
  channel: OwnedChannel;
  records: PerformanceDashboard["records"];
  summary: ReturnType<typeof summarizePerformance>;
  period: Period;
  loading: boolean;
  workspaceId: string;
}) {
  const latest = [...records].sort((a, b) => new Date(b.published_at).getTime() - new Date(a.published_at).getTime())[0];
  const metricCards = [
    { label: "曝光", value: formatCompactNumber(summary.exposure), helper: `${period} 天内 ${summary.published} 条内容`, icon: Eye },
    { label: "互动", value: formatCompactNumber(summary.interactions), helper: "赞、评论、收藏与转发", icon: Sparkles },
    { label: "互动率", value: formatRate(summary.engagementRate), helper: "互动 / 曝光", icon: BarChart3 },
    { label: "转化", value: summary.conversions.toLocaleString(), helper: "线索、订单或购买", icon: Target },
  ];
  return (
    <div className="mt-5 space-y-5">
      <section aria-label="账号核心指标" className="grid grid-cols-2 overflow-hidden rounded-xl border border-border bg-surface shadow-panel xl:grid-cols-4">
        {metricCards.map((item) => (
          <div className="border-r border-b border-border p-4 even:border-r-0 nth-[n+3]:border-b-0 xl:border-r xl:border-b-0 xl:p-5 xl:last:border-r-0" key={item.label}>
            <p className="flex items-center gap-2 text-xs text-text-muted"><item.icon size={14} />{item.label}</p>
            {loading ? <div className="mt-3 h-8 w-24 animate-pulse rounded bg-surface-subtle" /> : <strong className="mt-3 block text-2xl font-semibold tracking-tight tabular-nums">{item.value}</strong>}
            <p className="mt-1 text-[11px] text-text-muted">{item.helper}</p>
          </div>
        ))}
      </section>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_340px]">
        <section className="rounded-xl border border-border bg-surface p-5 shadow-panel">
          <div className="mb-5 flex items-start justify-between gap-4">
            <div><h2 className="text-sm font-semibold">表现趋势</h2><p className="mt-1 text-[11px] text-text-muted">对比每条发布内容的曝光与互动变化</p></div>
            <span className="text-[11px] text-text-muted">{latest ? `更新于 ${formatRelativeTime(latest.published_at)}` : "暂无数据"}</span>
          </div>
          {loading ? <div className="h-64 animate-pulse rounded-xl bg-surface-subtle" /> : <PerformanceTrendChart records={records} />}
        </section>
        <aside className="rounded-xl border border-border bg-surface p-5 shadow-panel">
          <div className="flex items-center gap-2"><Sparkles className="text-primary-600" size={16} /><h2 className="text-sm font-semibold">洞察与建议</h2></div>
          <InsightList platform={channel.platform} records={records} />
        </aside>
      </div>

      <section className="overflow-hidden rounded-xl border border-border bg-surface shadow-panel">
        <div className="flex items-center justify-between border-b border-border px-5 py-4">
          <div><h2 className="text-sm font-semibold">内容表现 Top 5</h2><p className="mt-1 text-[11px] text-text-muted">按曝光排名，同时保留平台原生指标</p></div>
        </div>
        <ContentPerformanceTable limit={5} records={records} workspaceId={workspaceId} />
      </section>
    </div>
  );
}

function ContentTab({
  channel,
  records,
  summary,
  loading,
  workspaceId,
}: {
  channel: OwnedChannel;
  records: PerformanceDashboard["records"];
  summary: ReturnType<typeof summarizePerformance>;
  loading: boolean;
  workspaceId: string;
}) {
  const nativeValues = records.map(nativeMetric);
  const bestNative = nativeValues[0];
  return (
    <div className="mt-5 space-y-5">
      <section className="grid gap-px overflow-hidden rounded-xl border border-border bg-border sm:grid-cols-2 lg:grid-cols-4">
        {[
          { label: "已复盘内容", value: records.length.toString(), helper: "当前时间范围" },
          { label: "单条平均曝光", value: formatCompactNumber(records.length ? summary.exposure / records.length : 0), helper: "用于识别稳定基线" },
          { label: "单条平均互动", value: formatCompactNumber(records.length ? summary.interactions / records.length : 0), helper: `互动率 ${formatRate(summary.engagementRate)}` },
          { label: bestNative?.label ?? "平台指标", value: bestNative?.value ?? "—", helper: `${platformLabel(channel.platform)} 原生指标示例` },
        ].map((item) => (
          <div className="bg-surface p-5" key={item.label}><p className="text-xs text-text-muted">{item.label}</p>{loading ? <div className="mt-3 h-7 w-20 animate-pulse rounded bg-surface-subtle" /> : <strong className="mt-2 block text-xl font-semibold tabular-nums">{item.value}</strong>}<p className="mt-1 text-[11px] text-text-muted">{item.helper}</p></div>
        ))}
      </section>
      <section className="overflow-hidden rounded-xl border border-border bg-surface shadow-panel">
        <div className="border-b border-border px-5 py-4"><h2 className="text-sm font-semibold">全部内容表现</h2><p className="mt-1 text-[11px] text-text-muted">按曝光从高到低排序，点击右侧按钮进入单条复盘。</p></div>
        <ContentPerformanceTable records={records} workspaceId={workspaceId} />
      </section>
    </div>
  );
}

function PositioningTab({ channel, canEdit, workspaceId }: { channel: OwnedChannel; canEdit: boolean; workspaceId: string }) {
  const save = useSavePositioning(workspaceId, channel.id);
  const [form, setForm] = useState<PositioningUpdate>({
    positioning: channel.positioning,
    audience: channel.audience,
    content_pillars: channel.content_pillars.map(String),
    tone_rules: channel.tone_rules.map(String),
    prohibited_topics: channel.prohibited_topics.map(String),
  });
  const audience = form.audience as Record<string, unknown>;
  const completed = [
    Boolean(channel.handle),
    Boolean(form.positioning.trim()),
    Boolean(String(audience.primary ?? "").trim()),
    form.content_pillars.length > 0,
    form.tone_rules.length > 0,
    form.prohibited_topics.length > 0,
  ];
  const score = Math.round((completed.filter(Boolean).length / completed.length) * 100);

  const setLines = (key: "content_pillars" | "tone_rules" | "prohibited_topics", value: string) =>
    setForm({ ...form, [key]: value.split("\n").map((item) => item.trim()).filter(Boolean) });

  return (
    <form className="mt-5 grid gap-5 xl:grid-cols-[minmax(0,1fr)_340px]" onSubmit={(event) => { event.preventDefault(); save.mutate(form); }}>
      <section className="space-y-5 rounded-xl border border-border bg-surface p-5 shadow-panel">
        <div><h2 className="text-sm font-semibold">账号策略档案</h2><p className="mt-1 text-xs leading-5 text-text-muted">这些规则会进入选题、脚本和审核上下文，同时作为表现分析的策略参照。</p></div>
        <label className="block text-sm font-medium">定位声明<textarea className={`${textareaClass} mt-2 min-h-28`} disabled={!canEdit} onChange={(event) => setForm({ ...form, positioning: event.target.value })} placeholder="帮助谁，用什么内容解决什么问题" value={form.positioning} /></label>
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="text-sm font-medium">核心受众<input className={`${inputClass} mt-2`} disabled={!canEdit} onChange={(event) => setForm({ ...form, audience: { ...audience, primary: event.target.value } })} placeholder="例如：5–30 人的品牌团队" value={String(audience.primary ?? "")} /></label>
          <label className="text-sm font-medium">核心问题<input className={`${inputClass} mt-2`} disabled={!canEdit} onChange={(event) => setForm({ ...form, audience: { ...audience, problem: event.target.value } })} placeholder="受众最想解决的问题" value={String(audience.problem ?? "")} /></label>
        </div>
        {[
          { label: "内容支柱", key: "content_pillars" as const, placeholder: "每行一个稳定内容方向" },
          { label: "语气与表达规则", key: "tone_rules" as const, placeholder: "每行一条可执行规则" },
          { label: "禁区与事实核查", key: "prohibited_topics" as const, placeholder: "每行一条风险或禁区" },
        ].map((item) => (
          <label className="block text-sm font-medium" key={item.key}>{item.label}<textarea className={`${textareaClass} mt-2`} disabled={!canEdit} onChange={(event) => setLines(item.key, event.target.value)} placeholder={item.placeholder} value={form[item.key].map(String).join("\n")} /></label>
        ))}
        <InlineError error={save.error} />
        {save.isSuccess ? <p className="flex items-center gap-2 text-xs font-medium text-success"><Check size={14} />定位规则已保存，后续内容生成将引用新版本。</p> : null}
        {canEdit ? <button className={primaryButton} disabled={save.isPending} type="submit"><Save size={15} />{save.isPending ? "正在保存…" : "保存定位"}</button> : null}
      </section>
      <aside className="space-y-4">
        <section className="rounded-xl border border-border bg-surface p-5 shadow-panel">
          <div className="flex items-center justify-between"><h2 className="text-sm font-semibold">定位完善度</h2><strong className="text-xl tabular-nums">{score}<span className="text-xs font-normal text-text-muted"> / 100</span></strong></div>
          <div aria-label={`定位完善度 ${score}%`} className="mt-4 h-2 overflow-hidden rounded-full bg-surface-subtle"><div className="h-full rounded-full bg-primary-600 transition-all" style={{ width: `${score}%` }} /></div>
          <div className="mt-4 space-y-2">
            {["账号 Handle", "定位声明", "核心受众", "内容支柱", "表达规则", "事实禁区"].map((label, index) => <p className="flex items-center justify-between text-xs" key={label}><span className="text-text-muted">{label}</span><span className={completed[index] ? "text-success" : "text-warning"}>{completed[index] ? "已完成" : "待补充"}</span></p>)}
          </div>
        </section>
        <section className="rounded-xl border border-primary-100 bg-primary-50 p-5 text-primary-700">
          <p className="flex items-center gap-2 text-sm font-semibold"><MousePointerClick size={16} />如何用于分析</p>
          <p className="mt-2 text-xs leading-5">数据概览回答「发生了什么」，定位档案帮助判断「是否符合我们想要的账号方向」。</p>
        </section>
      </aside>
    </form>
  );
}
