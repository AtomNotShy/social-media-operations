"use client";

import { ArrowRight, BarChart3, ExternalLink } from "lucide-react";
import Link from "next/link";
import { EmptyState } from "@/src/components/ui/empty-state";
import { ErrorState } from "@/src/components/ui/error-state";
import { PageHeader } from "@/src/components/ui/page-header";
import { usePerformance } from "@/src/features/production/queries";
import { MetricCard, SavedViewPicker } from "@/src/features/production/ui";

export function ReviewsPage({ workspaceId }: { workspaceId: string }) {
  const performance = usePerformance(workspaceId, 30);
  return <>
    <PageHeader eyebrow="发布复盘" title="内容表现" description="曝光、互动、转化分层展示；结果只来自已登记发布与复盘数据，不把预测当成表现。" actions={<SavedViewPicker entityType="reviews" workspaceId={workspaceId} />} />
    {performance.isLoading ? <div className="h-72 animate-pulse rounded-xl bg-surface" /> : performance.error || !performance.data ? <ErrorState message="复盘看板加载失败。" onRetry={() => performance.refetch()} /> : <>
      <div className="mb-5 grid grid-cols-2 gap-3 lg:grid-cols-5"><MetricCard label="已发布" value={performance.data.totals.published_count} /><MetricCard label="已复盘" value={performance.data.totals.review_count} /><MetricCard label="曝光" value={performance.data.totals.exposure.toLocaleString()} helper="浏览与展示机会" /><MetricCard label="互动" value={performance.data.totals.interactions.toLocaleString()} helper="赞评藏转" /><MetricCard label="转化" value={performance.data.totals.conversions.toLocaleString()} helper="线索、订单或购买" /></div>
      {performance.data.records.length ? <div className="overflow-hidden rounded-xl border border-border bg-surface shadow-panel"><div className="hidden grid-cols-[1.4fr_repeat(3,.7fr)_1fr] gap-4 border-b border-border bg-surface-subtle px-5 py-3 text-xs font-semibold text-text-muted md:grid"><span>发布记录</span><span>曝光</span><span>互动</span><span>转化</span><span>窗口</span></div>{performance.data.records.map((record) => <Link className="grid gap-3 border-b border-border px-5 py-4 last:border-0 hover:bg-surface-subtle md:grid-cols-[1.4fr_repeat(3,.7fr)_1fr] md:items-center" href={`/w/${workspaceId}/reviews/${record.publish_record_id}`} key={record.publish_record_id}><div><strong className="text-sm">{new Date(record.published_at).toLocaleString("zh-CN")}</strong><span className="mt-1 flex items-center gap-1 text-[11px] text-text-muted"><ExternalLink size={11} /> 已登记公开链接</span></div><Metric label="曝光" value={record.exposure} /><Metric label="互动" value={record.interactions} /><Metric label="转化" value={record.conversions} /><span className="flex items-center justify-between text-xs">{record.latest_review_window ?? "待复盘"}<ArrowRight size={14} /></span></Link>)}</div> : <section className="rounded-xl border border-border bg-surface"><EmptyState title="还没有发布表现" description="先从排期页生成发布包并登记真实发布结果。" /></section>}
      <div className="mt-4 flex items-start gap-3 rounded-xl border border-primary-100 bg-primary-50 p-4 text-xs leading-5 text-primary-700"><BarChart3 className="mt-0.5 shrink-0" size={16} /><p>当前统一搜索是可解释的关键词匹配；本看板也只汇总已录入指标。向量语义搜索和平台自动回传尚未被伪装成已完成能力。</p></div>
    </>}
  </>;
}
function Metric({ label, value }: { label: string; value: number }) { return <div><span className="text-[10px] text-text-muted md:hidden">{label}</span><strong className="block text-sm tabular-nums">{value.toLocaleString()}</strong></div>; }

