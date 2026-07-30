"use client";

import { AlertTriangle, ArrowRight, CalendarCheck, FileCheck2, Gauge, History } from "lucide-react";
import Link from "next/link";
import { ErrorState } from "@/src/components/ui/error-state";
import { PageHeader } from "@/src/components/ui/page-header";
import { StatusBadge } from "@/src/components/ui/status-badge";
import { useToday } from "@/src/features/production/queries";
import { MetricCard, secondaryButton } from "@/src/features/production/ui";

export function TodayPage({ workspaceId }: { workspaceId: string }) {
  const today = useToday(workspaceId);
  if (today.isLoading) return <p>正在整理今天的工作…</p>;
  if (today.error || !today.data) return <ErrorState message="今日工作台加载失败。" onRetry={() => today.refetch()} />;
  return <>
    <PageHeader eyebrow="工作区" title="今天必须处理的事" description={`按 ${today.data.timezone} 时区汇总；这里不展示无行动意义的泛化数据。`} />
    <div className="mb-5 grid grid-cols-2 gap-3 lg:grid-cols-4"><MetricCard label="今日截止项目" value={today.data.projects_due.length} helper="需要继续生产或审核" /><MetricCard label="今日待发布" value={today.data.publish_plans.length} helper="按排期时间排序" /><MetricCard label="待复盘发布" value={today.data.published_waiting_review_count} helper="至少补齐 24h 数据" /><MetricCard label="运行中任务" value={today.data.active_job_count} helper="失败项在任务中心处理" /></div>
    <div className="grid gap-5 xl:grid-cols-2">
      <TaskSection icon={FileCheck2} title="今日截止项目">{today.data.projects_due.length ? today.data.projects_due.map((project) => <TaskRow href={`/w/${workspaceId}/content-projects/${project.id}`} key={project.id} title={project.title} meta={project.due_at ? new Date(project.due_at).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" }) : "今天"} status={project.status} />) : <EmptyLine text="今天没有截止项目。" />}</TaskSection>
      <TaskSection icon={CalendarCheck} title="今日发布">{today.data.publish_plans.length ? today.data.publish_plans.map((plan) => <TaskRow href={`/w/${workspaceId}/schedule`} key={plan.id} title={String(plan.publish_payload.title ?? "未命名发布计划")} meta={new Date(plan.scheduled_at).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" })} status={plan.status} />) : <EmptyLine text="今天没有发布计划。" />}</TaskSection>
      <TaskSection icon={History} title="发布后待复盘"><div className="flex items-center justify-between rounded-lg bg-surface-subtle p-4"><div><strong className="text-sm">{today.data.published_waiting_review_count} 条发布记录</strong><p className="mt-1 text-xs text-text-muted">分别记录曝光、互动和转化。</p></div><Link className={secondaryButton} href={`/w/${workspaceId}/reviews`}>去复盘 <ArrowRight size={14} /></Link></div></TaskSection>
      <TaskSection icon={Gauge} title="任务与异常"><div className="flex items-center justify-between rounded-lg bg-surface-subtle p-4"><div><strong className="flex items-center gap-2 text-sm"><AlertTriangle size={15} /> {today.data.active_job_count} 个任务处理中</strong><p className="mt-1 text-xs text-text-muted">等待人工处理和重试的任务集中在任务中心。</p></div><Link className={secondaryButton} href={`/w/${workspaceId}/jobs`}>任务中心</Link></div></TaskSection>
    </div>
  </>;
}
function TaskSection({ icon: Icon, title, children }: { icon: typeof FileCheck2; title: string; children: React.ReactNode }) { return <section className="rounded-xl border border-border bg-surface p-5 shadow-panel"><h2 className="mb-4 flex items-center gap-2 font-semibold"><Icon className="text-primary-600" size={17} /> {title}</h2><div className="space-y-2">{children}</div></section>; }
function TaskRow({ title, meta, status, href }: { title: string; meta: string; status: string; href: string }) { return <Link className="flex items-center gap-3 rounded-lg border border-border p-3 hover:bg-surface-subtle" href={href}><div className="min-w-0 flex-1"><strong className="block truncate text-sm">{title}</strong><span className="mt-1 block text-xs text-text-muted">{meta}</span></div><StatusBadge label={status} status={status} /><ArrowRight size={15} /></Link>; }
function EmptyLine({ text }: { text: string }) { return <p className="rounded-lg bg-surface-subtle p-4 text-sm text-text-muted">{text}</p>; }

