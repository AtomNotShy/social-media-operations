"use client";

import { FileAudio, FileImage, FileText, FileVideo, Upload } from "lucide-react";
import { useState } from "react";
import { EmptyState } from "@/src/components/ui/empty-state";
import { ErrorState } from "@/src/components/ui/error-state";
import { PageHeader } from "@/src/components/ui/page-header";
import { useWorkspaceRole } from "@/src/features/identity/queries";
import { useAssets, useProjects, useUploadAsset } from "@/src/features/production/queries";
import { InlineError, inputClass, primaryButton } from "@/src/features/production/ui";

export function AssetsPage({ workspaceId, projectId }: { workspaceId: string; projectId?: string }) {
  const assets = useAssets(workspaceId, projectId);
  const projects = useProjects(workspaceId);
  const permission = useWorkspaceRole(workspaceId);
  const upload = useUploadAsset(workspaceId, projectId);
  const [file, setFile] = useState<File | null>(null);
  const [rights, setRights] = useState("");
  return <>
    <PageHeader eyebrow={projectId ? "内容项目" : "我的资料"} title={projectId ? "项目素材" : "素材库"} description="浏览器直接上传到对象存储，应用服务只签发上传意图并在完成后远端校验。每个文件必须保留版权或授权说明。" />
    {permission.canEdit ? <section className="mb-5 grid gap-3 rounded-xl border border-dashed border-primary-100 bg-primary-50/60 p-4 md:grid-cols-[1fr_1fr_auto] md:items-end">
      <label className="text-xs font-medium">选择文件<input className={`${inputClass} mt-2 bg-surface`} onChange={(event) => setFile(event.target.files?.[0] ?? null)} type="file" /></label>
      <label className="text-xs font-medium">版权 / 授权说明<input className={`${inputClass} mt-2 bg-surface`} onChange={(event) => setRights(event.target.value)} placeholder="来源、授权范围、到期时间" value={rights} /></label>
      <button className={primaryButton} disabled={!file || !rights.trim() || upload.isPending} onClick={() => file && upload.mutate({ file, rightsNote: rights }, { onSuccess: () => { setFile(null); setRights(""); } })} type="button"><Upload size={15} /> 直传素材</button>
      <div className="md:col-span-3"><InlineError error={upload.error} /></div>
    </section> : null}
    {assets.isLoading ? <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{Array.from({ length: 6 }).map((_, i) => <div className="h-44 animate-pulse rounded-xl bg-surface" key={i} />)}</div> : assets.error ? <ErrorState message="素材列表加载失败。" onRetry={() => assets.refetch()} /> : assets.data?.length ? <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{assets.data.map((asset) => { const Icon = asset.asset_type === "image" ? FileImage : asset.asset_type === "video" ? FileVideo : asset.asset_type === "audio" ? FileAudio : FileText; const project = projects.data?.find((item) => item.id === asset.content_project_id); return <article className="rounded-xl border border-border bg-surface p-5 shadow-panel" key={asset.id}><span className="grid size-11 place-items-center rounded-xl bg-primary-50 text-primary-600"><Icon size={20} /></span><h2 className="mt-4 truncate text-sm font-semibold" title={asset.storage_key}>{asset.storage_key.split("/").pop()}</h2><p className="mt-1 text-xs text-text-muted">{asset.mime_type} · {(asset.size_bytes / 1024 / 1024).toFixed(2)} MB</p><p className="mt-4 rounded-lg bg-surface-subtle p-3 text-xs leading-5">{asset.rights_note || "未填写版权说明"}</p><p className="mt-3 text-[11px] text-text-muted">{project?.title || "公共素材"} · {asset.source_type}</p></article>; })}</div> : <section className="rounded-xl border border-border bg-surface"><EmptyState title="还没有素材" description="上传图片、视频、音频或文档，并填写可追溯的授权说明。" /></section>}
  </>;
}

