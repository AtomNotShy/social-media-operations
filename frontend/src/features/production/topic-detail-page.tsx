"use client";

import { ArrowLeft, FolderPlus, Save } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { ErrorState } from "@/src/components/ui/error-state";
import { PageHeader } from "@/src/components/ui/page-header";
import { StatusBadge } from "@/src/components/ui/status-badge";
import { useWorkspaceRole } from "@/src/features/identity/queries";
import {
  useChannels,
  useCreateProject,
  useTopic,
  useUpdateTopic,
} from "@/src/features/production/queries";
import type { Topic, TopicUpdate } from "@/src/features/production/types";
import { topicStatus } from "@/src/features/production/topics-page";
import { InlineError, inputClass, primaryButton, secondaryButton, textareaClass } from "@/src/features/production/ui";
import { platformLabel } from "@/src/lib/format";

export function TopicDetailPage({ workspaceId, topicId }: { workspaceId: string; topicId: string }) {
  const topic = useTopic(workspaceId, topicId);
  const permission = useWorkspaceRole(workspaceId);

  if (topic.isLoading) return <p>正在加载选题…</p>;
  if (topic.error) return <ErrorState message="选题加载失败。" onRetry={() => topic.refetch()} />;
  return <TopicForm canEdit={permission.canEdit} current={topic.data!} workspaceId={workspaceId} />;
}

function TopicForm({ current, canEdit, workspaceId }: { current: Topic; canEdit: boolean; workspaceId: string }) {
  const channels = useChannels(workspaceId);
  const update = useUpdateTopic(workspaceId, current.id);
  const createProject = useCreateProject(workspaceId);
  const [form, setForm] = useState<TopicUpdate>({
    version: current.version,
    title: current.title,
    owned_channel_id: current.owned_channel_id,
    audience_problem: current.audience_problem,
    angle: current.angle,
    hook: current.hook,
    evidence_refs: current.evidence_refs.map(String),
    status: current.status as TopicUpdate["status"],
  });
  return (
    <>
      <PageHeader
        eyebrow="候选选题"
        title={current.title}
        description={`版本 ${current.version} · 修改会进行乐观锁校验，冲突时不会覆盖其他成员的内容。`}
        actions={<Link className={secondaryButton} href={`/w/${workspaceId}/topics`}><ArrowLeft size={15} /> 返回选题</Link>}
      />
      <div className="mb-4 flex items-center gap-3 rounded-xl border border-border bg-surface p-4">
        <StatusBadge label={topicStatus(current.status)} status={current.status} />
        <span className="text-xs text-text-muted">证据引用 {current.evidence_refs.length} 条</span>
      </div>
      <form
        className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_340px]"
        onSubmit={(event) => {
          event.preventDefault();
          update.mutate(form, { onSuccess: (saved) => setForm({ ...form, version: saved.version }) });
        }}
      >
        <section className="grid gap-4 rounded-xl border border-border bg-surface p-5 shadow-panel">
          <label className="text-sm font-medium">标题<input className={`${inputClass} mt-2`} disabled={!canEdit} onChange={(event) => setForm({ ...form, title: event.target.value })} value={form.title ?? ""} /></label>
          <label className="text-sm font-medium">目标账号<select className={`${inputClass} mt-2`} disabled={!canEdit} onChange={(event) => setForm({ ...form, owned_channel_id: event.target.value || null })} value={form.owned_channel_id ?? ""}><option value="">未指定</option>{channels.data?.map((channel) => <option key={channel.id} value={channel.id}>{channel.display_name} · {platformLabel(channel.platform)}</option>)}</select></label>
          {([["用户问题", "audience_problem"], ["切入角度", "angle"], ["开场钩子", "hook"]] as const).map(([label, key]) => <label className="text-sm font-medium" key={key}>{label}<textarea className={`${textareaClass} mt-2`} disabled={!canEdit} onChange={(event) => setForm({ ...form, [key]: event.target.value })} value={form[key] ?? ""} /></label>)}
          <InlineError error={update.error} />
          {canEdit ? <button className={primaryButton} disabled={update.isPending} type="submit"><Save size={15} /> 保存新版本</button> : null}
        </section>
        <aside className="space-y-4">
          <div className="rounded-xl border border-border bg-surface p-5">
            <h2 className="text-sm font-semibold">证据来源</h2>
            <div className="mt-3 space-y-2">{current.evidence_refs.length ? current.evidence_refs.map((ref) => <code className="block rounded-lg bg-surface-subtle p-2 text-[11px]" key={String(ref)}>{String(ref)}</code>) : <p className="text-xs text-text-muted">还没有证据引用。</p>}</div>
          </div>
          {canEdit && current.owned_channel_id ? (
            <button
              className={`${primaryButton} w-full`}
              disabled={createProject.isPending}
              onClick={() => createProject.mutate({ topic_id: current.id, owned_channel_id: current.owned_channel_id!, title: current.title }, { onSuccess: (created) => location.assign(`/w/${workspaceId}/content-projects/${created.id}`) })}
              type="button"
            >
              <FolderPlus size={15} /> 转成内容项目
            </button>
          ) : null}
          <InlineError error={createProject.error} />
        </aside>
      </form>
    </>
  );
}
