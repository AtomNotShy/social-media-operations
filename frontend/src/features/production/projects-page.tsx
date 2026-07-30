"use client";

import { ArrowRight, CalendarClock, FileText, Plus } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { EmptyState } from "@/src/components/ui/empty-state";
import { ErrorState } from "@/src/components/ui/error-state";
import { PageHeader } from "@/src/components/ui/page-header";
import { StatusBadge } from "@/src/components/ui/status-badge";
import { useWorkspaceRole } from "@/src/features/identity/queries";
import { useChannels, useCreateProject, useProjects, useTopics } from "@/src/features/production/queries";
import type { ContentProjectCreate } from "@/src/features/production/types";
import { Dialog, InlineError, SavedViewPicker, inputClass, primaryButton } from "@/src/features/production/ui";
import { formatRelativeTime } from "@/src/lib/format";

const statusFilters = ["", "idea", "scripting", "producing", "review", "scheduled", "published", "reviewing", "archived"];

export function ProjectsPage({ workspaceId }: { workspaceId: string }) {
  const router = useRouter();
  const params = useSearchParams();
  const status = params.get("status") || undefined;
  const projects = useProjects(workspaceId, status);
  const channels = useChannels(workspaceId);
  const permission = useWorkspaceRole(workspaceId);
  const [open, setOpen] = useState(false);
  return (
    <>
      <PageHeader
        eyebrow="内容生产"
        title="内容项目"
        description="从选题到脚本、素材、审核、排期与发布记录的单一工作单元。"
        actions={<div className="flex gap-2"><SavedViewPicker entityType="content_projects" workspaceId={workspaceId} />{permission.canEdit ? <button className={primaryButton} onClick={() => setOpen(true)} type="button"><Plus size={15} /> 新建项目</button> : null}</div>}
      />
      <div className="mb-4 flex gap-2 overflow-x-auto pb-1">
        {statusFilters.map((item) => <button className={`shrink-0 rounded-full border px-3 py-2 text-xs ${(status ?? "") === item ? "border-text bg-text text-white" : "border-border bg-surface"}`} key={item || "all"} onClick={() => { const next = new URLSearchParams(); if (item) next.set("status", item); router.replace(`?${next}`); }} type="button">{item ? projectStatus(item) : "全部"}</button>)}
      </div>
      {projects.isLoading ? <div className="space-y-3">{Array.from({ length: 4 }).map((_, i) => <div className="h-28 animate-pulse rounded-xl bg-surface" key={i} />)}</div> : projects.error ? <ErrorState message="内容项目加载失败。" onRetry={() => projects.refetch()} /> : projects.data?.length ? (
        <div className="space-y-3">
          {projects.data.map((project) => {
            const channel = channels.data?.find((item) => item.id === project.owned_channel_id);
            return <Link className="group flex flex-col gap-4 rounded-xl border border-border bg-surface p-5 shadow-panel transition hover:shadow-popover sm:flex-row sm:items-center" href={`/w/${workspaceId}/content-projects/${project.id}`} key={project.id}>
              <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-primary-50 text-primary-600"><FileText size={19} /></span>
              <div className="min-w-0 flex-1"><div className="flex flex-wrap items-center gap-2"><h2 className="font-semibold">{project.title}</h2><StatusBadge label={projectStatus(project.status)} status={project.status} /></div><p className="mt-1 text-xs text-text-muted">{channel?.display_name ?? "未知账号"} · 版本 {project.version} · {formatRelativeTime(project.updated_at)}</p></div>
              <div className="flex items-center gap-2 text-xs text-text-muted"><CalendarClock size={14} />{project.due_at ? new Date(project.due_at).toLocaleString("zh-CN", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) : "未设截止时间"}<ArrowRight className="ml-2 transition group-hover:translate-x-1" size={16} /></div>
            </Link>;
          })}
        </div>
      ) : <section className="rounded-xl border border-border bg-surface"><EmptyState title="没有符合条件的项目" description="从已选选题创建项目，或直接创建一个项目。" /></section>}
      <CreateProjectDialog workspaceId={workspaceId} open={open} onClose={() => setOpen(false)} />
    </>
  );
}

function CreateProjectDialog({ workspaceId, open, onClose }: { workspaceId: string; open: boolean; onClose: () => void }) {
  const channels = useChannels(workspaceId);
  const topics = useTopics(workspaceId, "selected");
  const create = useCreateProject(workspaceId);
  const [value, setValue] = useState<ContentProjectCreate>({ title: "", owned_channel_id: "" });
  return <Dialog open={open} onClose={onClose} title="新建内容项目" description="选择账号后，项目会继承对应定位约束。"><form className="grid gap-4" onSubmit={(event) => { event.preventDefault(); create.mutate(value, { onSuccess: onClose }); }}>
    <label className="text-sm font-medium">项目名称<input className={`${inputClass} mt-2`} required value={value.title} onChange={(event) => setValue({ ...value, title: event.target.value })} /></label>
    <label className="text-sm font-medium">目标账号<select className={`${inputClass} mt-2`} required value={value.owned_channel_id} onChange={(event) => setValue({ ...value, owned_channel_id: event.target.value })}><option value="">请选择</option>{channels.data?.filter((item) => item.active).map((item) => <option key={item.id} value={item.id}>{item.display_name}</option>)}</select></label>
    <label className="text-sm font-medium">来源选题<select className={`${inputClass} mt-2`} value={value.topic_id ?? ""} onChange={(event) => { const topic = topics.data?.find((item) => item.id === event.target.value); setValue({ ...value, topic_id: event.target.value || null, title: value.title || topic?.title || "" }); }}><option value="">无</option>{topics.data?.map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}</select></label>
    <label className="text-sm font-medium">截止时间<input className={`${inputClass} mt-2`} type="datetime-local" onChange={(event) => setValue({ ...value, due_at: event.target.value ? new Date(event.target.value).toISOString() : null })} /></label>
    <InlineError error={create.error} /><button className={primaryButton} disabled={create.isPending} type="submit">创建项目</button>
  </form></Dialog>;
}

export function projectStatus(status: string) {
  return ({ idea: "待开始", scripting: "写脚本", producing: "制作中", review: "待审核", scheduled: "已排期", published: "已发布", reviewing: "复盘中", archived: "已归档" }[status] ?? status);
}

