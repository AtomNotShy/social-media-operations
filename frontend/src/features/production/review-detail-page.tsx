"use client";

import { ArrowLeft, ExternalLink, Save } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";
import { ErrorState } from "@/src/components/ui/error-state";
import { PageHeader } from "@/src/components/ui/page-header";
import { useWorkspaceRole } from "@/src/features/identity/queries";
import { useCreateReview, usePublishRecord, useRecordReviews } from "@/src/features/production/queries";
import { InlineError, inputClass, primaryButton, secondaryButton, textareaClass } from "@/src/features/production/ui";

export function ReviewDetailPage({ workspaceId, recordId }: { workspaceId: string; recordId: string }) {
  const record = usePublishRecord(workspaceId, recordId);
  const reviews = useRecordReviews(workspaceId, recordId);
  const create = useCreateReview(workspaceId, recordId);
  const permission = useWorkspaceRole(workspaceId);
  const [windowName, setWindowName] = useState<"24h" | "7d" | "30d" | "manual">("24h");
  const [metrics, setMetrics] = useState<Record<string, string>>({ impressions: "", views: "", likes: "", comments: "", favorites: "", shares: "", leads: "", orders: "" });
  const [analysis, setAnalysis] = useState("");
  const [nextActions, setNextActions] = useState("");
  const totals = useMemo(() => ({
    exposure: Number(metrics.impressions || 0) + Number(metrics.views || 0),
    interactions: ["likes", "comments", "favorites", "shares"].reduce((sum, key) => sum + Number(metrics[key as keyof typeof metrics] || 0), 0),
    conversions: Number(metrics.leads || 0) + Number(metrics.orders || 0),
  }), [metrics]);
  if (record.isLoading || reviews.isLoading) return <p>正在加载复盘记录…</p>;
  if (record.error || reviews.error || !record.data) return <ErrorState message="发布复盘加载失败。" onRetry={() => { record.refetch(); reviews.refetch(); }} />;
  return <>
    <PageHeader eyebrow="发布复盘" title={`发布于 ${new Date(record.data.published_at).toLocaleString("zh-CN")}`} description="先录入原始指标，再写判断与下一步实验；历史窗口不会被覆盖。" actions={<Link className={secondaryButton} href={`/w/${workspaceId}/reviews`}><ArrowLeft size={15} /> 返回复盘</Link>} />
    <a className="mb-5 inline-flex items-center gap-2 text-sm font-medium text-primary-600" href={record.data.published_url} rel="noreferrer" target="_blank"><ExternalLink size={15} /> 查看真实发布链接</a>
    <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_380px]">
      <section className="rounded-xl border border-border bg-surface p-5 shadow-panel">
        <div className="flex flex-wrap gap-2">{(["24h", "7d", "30d", "manual"] as const).map((item) => <button className={`rounded-full border px-3 py-2 text-xs ${windowName === item ? "border-text bg-text text-white" : "border-border"}`} key={item} onClick={() => setWindowName(item)} type="button">{item}</button>)}</div>
        <div className="mt-5 grid gap-4 sm:grid-cols-2"><MetricGroup title="曝光" keys={["impressions", "views"]} labels={["展示", "播放"]} metrics={metrics} setMetrics={setMetrics} /><MetricGroup title="互动" keys={["likes", "comments", "favorites", "shares"]} labels={["点赞", "评论", "收藏", "分享"]} metrics={metrics} setMetrics={setMetrics} /><MetricGroup title="转化" keys={["leads", "orders"]} labels={["线索", "订单"]} metrics={metrics} setMetrics={setMetrics} /></div>
        <div className="mt-4 grid grid-cols-3 gap-3">{Object.entries(totals).map(([key, value]) => <div className="rounded-lg bg-surface-subtle p-3" key={key}><p className="text-[10px] text-text-muted">{({ exposure: "曝光", interactions: "互动", conversions: "转化" } as Record<string,string>)[key]}</p><strong className="mt-1 block">{value.toLocaleString()}</strong></div>)}</div>
        <label className="mt-4 block text-sm font-medium">分析与基线比较<textarea className={`${textareaClass} mt-2`} onChange={(event) => setAnalysis(event.target.value)} placeholder="假设是否成立？相对基线发生了什么？" value={analysis} /></label>
        <label className="mt-4 block text-sm font-medium">下一步行动<textarea className={`${textareaClass} mt-2 min-h-20`} onChange={(event) => setNextActions(event.target.value)} placeholder="每行一个动作" value={nextActions} /></label>
        <InlineError error={create.error} />
        {permission.canEdit ? <button className={`${primaryButton} mt-4`} onClick={() => create.mutate({ review_window: windowName, metrics: Object.fromEntries(Object.entries(metrics).filter(([, value]) => value !== "").map(([key, value]) => [key, Number(value)])), analysis: { conclusion: analysis }, next_actions: nextActions.split("\n").map((item) => item.trim()).filter(Boolean) }, { onSuccess: () => { setAnalysis(""); setNextActions(""); } })} type="button"><Save size={15} /> 保存复盘窗口</button> : null}
      </section>
      <aside className="space-y-4"><h2 className="text-sm font-semibold">历史复盘</h2>{reviews.data?.length ? reviews.data.map((review) => <article className="rounded-xl border border-border bg-surface p-4" key={review.id}><div className="flex items-center justify-between"><strong className="text-sm">{review.review_window}</strong><span className="text-[11px] text-text-muted">{new Date(review.created_at).toLocaleDateString("zh-CN")}</span></div><p className="mt-3 text-xs leading-5">{String(review.analysis.outcome ?? review.analysis.conclusion ?? "已记录指标，待补充结论。")}</p><ul className="mt-3 space-y-1 text-xs text-text-muted">{review.next_actions.map((item) => <li key={String(item)}>• {String(item)}</li>)}</ul></article>) : <p className="rounded-xl bg-surface-subtle p-4 text-sm text-text-muted">还没有复盘窗口。</p>}</aside>
    </div>
  </>;
}
function MetricGroup({ title, keys, labels, metrics, setMetrics }: { title: string; keys: string[]; labels: string[]; metrics: Record<string,string>; setMetrics: (value: typeof metrics) => void }) { return <fieldset className="rounded-xl border border-border p-4"><legend className="px-1 text-xs font-semibold">{title}</legend><div className="grid grid-cols-2 gap-3">{keys.map((key, index) => <label className="text-[11px] text-text-muted" key={key}>{labels[index]}<input className={`${inputClass} mt-1`} min="0" onChange={(event) => setMetrics({ ...metrics, [key]: event.target.value })} type="number" value={metrics[key]} /></label>)}</div></fieldset>; }
