"use client";

import { FlaskConical, Plus, Users } from "lucide-react";
import { useState } from "react";
import { EmptyState } from "@/src/components/ui/empty-state";
import { ErrorState } from "@/src/components/ui/error-state";
import { PageHeader } from "@/src/components/ui/page-header";
import { StatusBadge } from "@/src/components/ui/status-badge";
import { useWorkspaceRole } from "@/src/features/identity/queries";
import { useCreateExperiment, useExperiments } from "@/src/features/production/queries";
import type { ExperimentCreate } from "@/src/features/production/types";
import { Dialog, InlineError, inputClass, primaryButton, textareaClass } from "@/src/features/production/ui";

export function ExperimentsPage({ workspaceId }: { workspaceId: string }) {
  const experiments = useExperiments(workspaceId);
  const permission = useWorkspaceRole(workspaceId);
  const [open, setOpen] = useState(false);
  return <>
    <PageHeader eyebrow="P3 效率增强" title="运营实验" description="冻结假设、主指标和版本分组；归因事件按曝光、互动、转化记录，避免用高赞替代业务结论。" actions={permission.canEdit ? <button className={primaryButton} onClick={() => setOpen(true)} type="button"><Plus size={15} /> 新建实验</button> : null} />
    <div className="mb-4 flex items-start gap-3 rounded-xl border border-primary-100 bg-primary-50 p-4 text-xs leading-5 text-primary-700"><Users className="mt-0.5 shrink-0" size={16} /><p>项目负责人、共享保存视图和实验分组构成当前协作闭环。独立通知中心尚无后端契约，因此前端不会伪造“提醒已发送”。</p></div>
    {experiments.isLoading ? <div className="h-64 animate-pulse rounded-xl bg-surface" /> : experiments.error ? <ErrorState message="实验列表加载失败。" onRetry={() => experiments.refetch()} /> : experiments.data?.length ? <div className="grid gap-4 lg:grid-cols-2">{experiments.data.map((experiment) => <article className="rounded-xl border border-border bg-surface p-5 shadow-panel" key={experiment.id}><div className="flex items-start justify-between"><span className="grid size-10 place-items-center rounded-xl bg-primary-50 text-primary-600"><FlaskConical size={18} /></span><StatusBadge label={experiment.status === "running" ? "运行中" : experiment.status} status={experiment.status} /></div><h2 className="mt-4 font-semibold">{experiment.name}</h2><p className="mt-2 text-sm leading-6 text-text-muted">{experiment.hypothesis}</p><p className="mt-4 text-xs"><span className="text-text-muted">主指标：</span>{experiment.primary_metric}</p><div className="mt-3 flex flex-wrap gap-2">{experiment.variants.map((variant) => <span className="rounded-full bg-surface-subtle px-3 py-1.5 text-xs" key={variant.key}>{variant.name}</span>)}</div><p className="mt-4 border-t border-border pt-3 text-[11px] text-text-muted">定义版本 {experiment.version} · 开始后不可修改假设和指标</p></article>)}</div> : <section className="rounded-xl border border-border bg-surface"><EmptyState title="还没有运营实验" description="先定义一个可证伪假设、主指标和至少两个版本。" /></section>}
    <CreateExperimentDialog workspaceId={workspaceId} open={open} onClose={() => setOpen(false)} />
  </>;
}
function CreateExperimentDialog({ workspaceId, open, onClose }: { workspaceId: string; open: boolean; onClose: () => void }) {
  const create = useCreateExperiment(workspaceId);
  const [value, setValue] = useState<ExperimentCreate>({ name: "", hypothesis: "", primary_metric: "conversion_rate", variants: [{ key: "a", name: "版本 A" }, { key: "b", name: "版本 B" }] });
  return <Dialog open={open} onClose={onClose} title="新建运营实验"><form className="grid gap-4" onSubmit={(event) => { event.preventDefault(); create.mutate(value, { onSuccess: onClose }); }}><label className="text-sm font-medium">实验名称<input className={`${inputClass} mt-2`} required value={value.name} onChange={(event) => setValue({ ...value, name: event.target.value })} /></label><label className="text-sm font-medium">可证伪假设<textarea className={`${textareaClass} mt-2`} required value={value.hypothesis} onChange={(event) => setValue({ ...value, hypothesis: event.target.value })} /></label><label className="text-sm font-medium">主指标<input className={`${inputClass} mt-2`} required value={value.primary_metric} onChange={(event) => setValue({ ...value, primary_metric: event.target.value })} /></label><InlineError error={create.error} /><button className={primaryButton} disabled={create.isPending} type="submit">创建草稿实验</button></form></Dialog>;
}

