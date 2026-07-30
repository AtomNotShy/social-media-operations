"use client";

import { CalendarCheck, CheckCircle2, ClipboardCopy, ExternalLink, PackageCheck, Plus } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { useMemo, useState } from "react";
import { EmptyState } from "@/src/components/ui/empty-state";
import { ErrorState } from "@/src/components/ui/error-state";
import { PageHeader } from "@/src/components/ui/page-header";
import { StatusBadge } from "@/src/components/ui/status-badge";
import { useWorkspaceRole } from "@/src/features/identity/queries";
import { useChannels, useCreatePlan, usePlanActions, usePlans, useProjects } from "@/src/features/production/queries";
import type { PublishPackage, PublishPlan, PublishPlanCreate } from "@/src/features/production/types";
import { Dialog, InlineError, SavedViewPicker, inputClass, primaryButton, secondaryButton } from "@/src/features/production/ui";

const defaultScheduleAt = new Date(Date.now() + 86_400_000).toISOString();

export function SchedulePage({ workspaceId }: { workspaceId: string }) {
  const params = useSearchParams();
  const plans = usePlans(workspaceId, params.get("status") || undefined);
  const projects = useProjects(workspaceId);
  const channels = useChannels(workspaceId);
  const permission = useWorkspaceRole(workspaceId);
  const actions = usePlanActions(workspaceId);
  const [createOpen, setCreateOpen] = useState(Boolean(params.get("project")));
  const [activePlan, setActivePlan] = useState<PublishPlan | null>(null);
  const [publishPackage, setPublishPackage] = useState<PublishPackage | null>(null);
  const [recordOpen, setRecordOpen] = useState(false);
  const grouped = useMemo(() => {
    const result = new Map<string, PublishPlan[]>();
    plans.data?.forEach((plan) => {
      const day = new Date(plan.scheduled_at).toLocaleDateString("zh-CN", { weekday: "long", month: "long", day: "numeric" });
      result.set(day, [...(result.get(day) ?? []), plan]);
    });
    return [...result.entries()];
  }, [plans.data]);

  function openPackage(plan: PublishPlan) {
    actions.package.mutate(plan, {
      onSuccess: (value) => {
        setActivePlan(plan);
        setPublishPackage(value);
      },
    });
  }

  return <>
    <PageHeader eyebrow="审核与发布" title="内容排期" description="排期按日期分组；只有审核通过的人工发布计划才能生成发布包并登记真实发布结果。" actions={<div className="flex gap-2"><SavedViewPicker entityType="publish_plans" workspaceId={workspaceId} />{permission.canEdit ? <button className={primaryButton} onClick={() => setCreateOpen(true)} type="button"><Plus size={15} /> 新建排期</button> : null}</div>} />
    <div className="mb-5 grid grid-cols-2 gap-3 lg:grid-cols-4">
      {[
        ["全部", plans.data?.length ?? 0],
        ["待审核", plans.data?.filter((item) => item.status === "draft").length ?? 0],
        ["可发布", plans.data?.filter((item) => ["approved", "queued"].includes(item.status)).length ?? 0],
        ["已发布", plans.data?.filter((item) => item.status === "published").length ?? 0],
      ].map(([label, value]) => <div className="rounded-xl border border-border bg-surface p-4" key={String(label)}><p className="text-xs text-text-muted">{label}</p><strong className="mt-2 block text-2xl">{value}</strong></div>)}
    </div>
    {plans.isLoading ? <div className="space-y-4">{Array.from({ length: 5 }).map((_, i) => <div className="h-32 animate-pulse rounded-xl bg-surface" key={i} />)}</div> : plans.error ? <ErrorState message="排期加载失败。" onRetry={() => plans.refetch()} /> : grouped.length ? <div className="space-y-6">{grouped.map(([day, items]) => <section key={day}><h2 className="mb-3 text-lg font-semibold">{day}</h2><div className="space-y-3">{items.map((plan) => {
      const project = projects.data?.find((item) => item.id === plan.content_project_id);
      const channel = channels.data?.find((item) => item.id === plan.owned_channel_id);
      return <article className="flex flex-col gap-4 rounded-xl border border-border bg-surface p-4 shadow-panel md:flex-row md:items-center" key={plan.id}><div className="grid min-w-20 place-items-center rounded-xl bg-surface-subtle p-3 text-center"><strong className="text-xl">{new Date(plan.scheduled_at).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" })}</strong><span className="text-[10px] text-text-muted">{channel?.platform ?? "平台"}</span></div><div className="min-w-0 flex-1"><div className="flex flex-wrap items-center gap-2"><h3 className="font-semibold">{project?.title ?? "未知项目"}</h3><StatusBadge label={planStatus(plan.status)} status={plan.status} /></div><p className="mt-1 text-xs text-text-muted">{channel?.display_name ?? "未知账号"} · {plan.publishing_mode === "manual" ? "人工发布" : "官方接口"}</p></div>{permission.canEdit ? <div className="flex flex-wrap gap-2">{plan.status === "draft" ? <button className={secondaryButton} disabled={actions.approve.isPending} onClick={() => actions.approve.mutate(plan)} type="button"><CheckCircle2 size={14} /> 审核通过</button> : null}{["approved", "queued"].includes(plan.status) ? <button className={primaryButton} onClick={() => openPackage(plan)} type="button"><PackageCheck size={14} /> 发布包</button> : null}</div> : null}</article>;
    })}</div></section>)}</div> : <section className="rounded-xl border border-border bg-surface"><EmptyState title="还没有排期" description="先让内容项目进入待审核状态，再创建人工发布计划。" /></section>}
    <InlineError error={actions.approve.error || actions.package.error} />
    <CreatePlanDialog workspaceId={workspaceId} defaultProject={params.get("project") || undefined} open={createOpen} onClose={() => setCreateOpen(false)} />
    <Dialog open={Boolean(publishPackage)} onClose={() => { setPublishPackage(null); setActivePlan(null); }} title="人工发布包" description="复制文案和素材清单到平台；只有登记 URL 与发布时间后才会显示为已发布。">
      {publishPackage ? <div className="space-y-4"><div className="rounded-xl bg-surface-subtle p-4"><p className="text-xs font-semibold text-text-muted">发布文案</p><pre className="mt-2 whitespace-pre-wrap font-sans text-sm leading-6">{publishPackage.latest_script.body}</pre><button className={`${secondaryButton} mt-3`} onClick={() => navigator.clipboard.writeText(publishPackage.latest_script.body)} type="button"><ClipboardCopy size={14} /> 复制脚本</button></div><div className="rounded-xl border border-border p-4"><p className="text-sm font-semibold">平台字段</p><pre className="mt-2 overflow-auto text-xs leading-5">{JSON.stringify(publishPackage.payload, null, 2)}</pre></div><div className="rounded-xl border border-border p-4"><p className="text-sm font-semibold">素材清单 · {publishPackage.assets.length}</p><ul className="mt-2 space-y-1 text-xs text-text-muted">{publishPackage.assets.map((asset, index) => <li key={String((asset as { id?: string }).id ?? index)}>• {String((asset as { storage_key?: string }).storage_key ?? "素材")}</li>)}</ul></div><button className={`${primaryButton} w-full`} onClick={() => setRecordOpen(true)} type="button"><ExternalLink size={15} /> 已在平台发布，登记结果</button></div> : null}
    </Dialog>
    <RecordPublishDialog activePlan={activePlan} publishPackage={publishPackage} actions={actions} open={recordOpen} onClose={() => setRecordOpen(false)} onDone={() => { setRecordOpen(false); setPublishPackage(null); setActivePlan(null); }} />
  </>;
}

function CreatePlanDialog({ workspaceId, defaultProject, open, onClose }: { workspaceId: string; defaultProject?: string; open: boolean; onClose: () => void }) {
  const projects = useProjects(workspaceId);
  const create = useCreatePlan(workspaceId);
  const initialProject = projects.data?.find((item) => item.id === defaultProject);
  const [value, setValue] = useState<PublishPlanCreate>({ content_project_id: defaultProject ?? "", owned_channel_id: initialProject?.owned_channel_id ?? "", scheduled_at: defaultScheduleAt, publishing_mode: "manual", publish_payload: { title: "", hashtags: [] } });
  return <Dialog open={open} onClose={onClose} title="新建发布排期"><form className="grid gap-4" onSubmit={(event) => { event.preventDefault(); create.mutate(value, { onSuccess: onClose }); }}>
    <label className="text-sm font-medium">内容项目<select className={`${inputClass} mt-2`} required value={value.content_project_id} onChange={(event) => { const project = projects.data?.find((item) => item.id === event.target.value); setValue({ ...value, content_project_id: event.target.value, owned_channel_id: project?.owned_channel_id ?? "" }); }}><option value="">请选择</option>{projects.data?.filter((item) => ["producing", "review"].includes(item.status)).map((item) => <option key={item.id} value={item.id}>{item.title} · {item.status === "review" ? "待审核" : "制作中"}</option>)}</select></label>
    <label className="text-sm font-medium">发布时间<input className={`${inputClass} mt-2`} required type="datetime-local" onChange={(event) => setValue({ ...value, scheduled_at: new Date(event.target.value).toISOString() })} /></label>
    <label className="text-sm font-medium">发布标题<input className={`${inputClass} mt-2`} onChange={(event) => setValue({ ...value, publish_payload: { ...value.publish_payload, title: event.target.value } })} /></label>
    <InlineError error={create.error} /><button className={primaryButton} disabled={!value.content_project_id || create.isPending} type="submit"><CalendarCheck size={15} /> 保存草稿排期</button>
  </form></Dialog>;
}

function RecordPublishDialog({ activePlan, publishPackage, actions, open, onClose, onDone }: { activePlan: PublishPlan | null; publishPackage: PublishPackage | null; actions: ReturnType<typeof usePlanActions>; open: boolean; onClose: () => void; onDone: () => void }) {
  const [url, setUrl] = useState("");
  const [platformId, setPlatformId] = useState("");
  const [matched, setMatched] = useState(true);
  return <Dialog open={open} onClose={onClose} title="登记真实发布结果"><div className="grid gap-4"><label className="text-sm font-medium">公开 HTTPS 链接<input className={`${inputClass} mt-2`} placeholder="https://…" required value={url} onChange={(event) => setUrl(event.target.value)} /></label><label className="text-sm font-medium">平台内容 ID（可选）<input className={`${inputClass} mt-2`} value={platformId} onChange={(event) => setPlatformId(event.target.value)} /></label><label className="flex items-start gap-3 rounded-lg bg-surface-subtle p-3 text-sm"><input checked={matched} className="mt-1" onChange={(event) => setMatched(event.target.checked)} type="checkbox" /><span>实际发布内容与此发布包一致。若临时改稿，请取消勾选以保留证据。</span></label><InlineError error={actions.mark.error} /><button className={primaryButton} disabled={!activePlan || !publishPackage || !url.startsWith("https://") || actions.mark.isPending} onClick={() => activePlan && publishPackage && actions.mark.mutate({ plan: activePlan, input: { version: publishPackage.plan_version, published_url: url, published_at: new Date().toISOString(), platform_content_id: platformId || null, matched_publish_package: matched } }, { onSuccess: onDone })} type="button"><CheckCircle2 size={15} /> 确认已发布</button></div></Dialog>;
}

function planStatus(status: string) { return ({ draft: "待审核", approved: "已审核", queued: "发布包已生成", published: "已发布", failed: "失败", cancelled: "已取消" }[status] ?? status); }
