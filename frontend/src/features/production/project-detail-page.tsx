"use client";

import {
  ArrowLeft,
  CalendarPlus,
  ChevronRight,
  FilePenLine,
  FolderOpen,
  Image,
  PencilLine,
  Trash2,
  Video,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ErrorState } from "@/src/components/ui/error-state";
import { PageHeader } from "@/src/components/ui/page-header";
import { StatusBadge } from "@/src/components/ui/status-badge";
import { useWorkspaceRole } from "@/src/features/identity/queries";
import { downloadVideoArtifact } from "@/src/features/production/api";
import {
  useAssets,
  useChannels,
  useDeleteProject,
  useProject,
  useRequestVideo,
  useScripts,
  useTransitionProject,
  useVideoRuns,
} from "@/src/features/production/queries";
import {
  DeleteProjectDialog,
  EditProjectDialog,
} from "@/src/features/production/project-dialogs";
import { projectStatus } from "@/src/features/production/projects-page";
import {
  InlineError,
  primaryButton,
  secondaryButton,
} from "@/src/features/production/ui";

const nextStatus: Record<string, string> = {
  idea: "scripting",
  scripting: "producing",
  producing: "review",
  review: "scheduled",
  scheduled: "published",
  published: "reviewing",
  reviewing: "archived",
};

export function ProjectDetailPage({
  workspaceId,
  projectId,
}: {
  workspaceId: string;
  projectId: string;
}) {
  const router = useRouter();
  const project = useProject(workspaceId, projectId);
  const channels = useChannels(workspaceId);
  const scripts = useScripts(workspaceId, projectId);
  const assets = useAssets(workspaceId, projectId);
  const videos = useVideoRuns(workspaceId, projectId);
  const requestVideo = useRequestVideo(workspaceId, projectId);
  const transition = useTransitionProject(workspaceId, projectId);
  const remove = useDeleteProject(workspaceId, projectId);
  const [editing, setEditing] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const permission = useWorkspaceRole(workspaceId);
  if (project.isLoading) return <p>正在加载内容项目…</p>;
  if (project.error || !project.data)
    return (
      <ErrorState
        message="内容项目加载失败。"
        onRetry={() => project.refetch()}
      />
    );
  const item = project.data;
  const channel = channels.data?.find(
    (candidate) => candidate.id === item.owned_channel_id,
  );
  const target = nextStatus[item.status];
  return (
    <>
      <PageHeader
        eyebrow="内容项目"
        title={item.title}
        description={`${channel?.display_name ?? "未知账号"} · 版本 ${item.version} · ${item.due_at ? `截止 ${new Date(item.due_at).toLocaleString("zh-CN")}` : "未设置截止时间"}`}
        actions={
          <div className="flex gap-2">
            {permission.canEdit ? (
              <>
                <button
                  className={secondaryButton}
                  onClick={() => setEditing(true)}
                  type="button"
                >
                  <PencilLine size={15} /> 编辑
                </button>
                <button
                  className="inline-flex min-h-10 items-center justify-center gap-2 rounded-lg bg-danger px-4 py-2 text-sm font-medium text-white transition hover:bg-danger/90 disabled:cursor-not-allowed disabled:opacity-50"
                  onClick={() => setDeleting(true)}
                  type="button"
                >
                  <Trash2 size={15} /> 删除
                </button>
              </>
            ) : null}
            <Link
              className={secondaryButton}
              href={`/w/${workspaceId}/content-projects`}
            >
              <ArrowLeft size={15} /> 返回项目
            </Link>
          </div>
        }
      />
      <section className="mb-5 flex flex-col gap-4 rounded-xl border border-border bg-surface p-5 shadow-panel sm:flex-row sm:items-center">
        <div className="flex-1">
          <StatusBadge
            label={projectStatus(item.status)}
            status={item.status}
          />
          <p className="mt-2 text-xs leading-5 text-text-muted">
            状态推进由后端状态机校验；版本冲突时页面保留当前数据并要求刷新。
          </p>
        </div>
        {permission.canEdit && target ? (
          <button
            className={primaryButton}
            disabled={transition.isPending}
            onClick={() =>
              transition.mutate({
                from: item.status,
                to: target,
                version: item.version,
              })
            }
            type="button"
          >
            推进到「{projectStatus(target)}」<ChevronRight size={15} />
          </button>
        ) : null}
      </section>
      <InlineError error={transition.error} />
      <section className="mt-5 rounded-xl border border-border bg-surface p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="flex items-center gap-2 font-semibold">
              <Video size={17} /> 本地视频生成
            </h2>
            <p className="mt-1 text-xs leading-5 text-text-muted">
              使用最新脚本创建后台视频任务；需要独立启动 video worker，并配置
              MiniMax 或 ElevenLabs。
            </p>
          </div>
          {permission.canEdit && scripts.data?.[0] ? (
            <button
              className={primaryButton}
              disabled={requestVideo.isPending}
              onClick={() =>
                requestVideo.mutate({ scriptVersionId: scripts.data![0].id })
              }
              type="button"
            >
              {requestVideo.isPending ? "正在创建…" : "生成视频"}
            </button>
          ) : null}
        </div>
        <InlineError error={requestVideo.error} />
        {videos.data?.length ? (
          <div className="mt-4 space-y-2">
            {videos.data.slice(0, 3).map((run) => (
              <div
                className="flex flex-wrap items-center justify-between gap-3 rounded-lg bg-surface-subtle px-3 py-2 text-sm"
                key={run.id}
              >
                <span className="flex items-center gap-2">
                  <StatusBadge
                    label={
                      run.status === "succeeded"
                        ? "已完成"
                        : run.status === "failed"
                          ? "失败"
                          : run.status === "running"
                            ? "渲染中"
                            : "等待中"
                    }
                    status={run.status}
                  />{" "}
                  <span className="text-text-muted">
                    {new Date(run.created_at).toLocaleString("zh-CN")}
                  </span>
                </span>
                {run.status === "succeeded" ? (
                  <button
                    className="text-xs font-medium text-primary-600"
                    onClick={async () => {
                      const blob = await downloadVideoArtifact(
                        workspaceId,
                        projectId,
                        run.id,
                      );
                      const url = URL.createObjectURL(blob);
                      const link = document.createElement("a");
                      link.href = url;
                      link.download = `${run.id}.mp4`;
                      link.click();
                      URL.revokeObjectURL(url);
                    }}
                    type="button"
                  >
                    下载 MP4
                  </button>
                ) : run.error_message ? (
                  <span className="max-w-md text-xs text-danger-600">
                    {run.error_message}
                  </span>
                ) : null}
              </div>
            ))}
          </div>
        ) : (
          <p className="mt-4 text-sm text-text-muted">尚未创建视频任务。</p>
        )}
      </section>
      <div className="grid gap-4 lg:grid-cols-3">
        <ProjectArea
          icon={FilePenLine}
          title="脚本版本"
          value={`${scripts.data?.length ?? 0} 个版本`}
          description={
            scripts.data?.[0]?.change_note || "每次保存追加版本，不覆盖历史。"
          }
          href={`/w/${workspaceId}/content-projects/${projectId}/script`}
        />
        <ProjectArea
          icon={Image}
          title="项目素材"
          value={`${assets.data?.length ?? 0} 个文件`}
          description="对象存储直传，保留版权与授权说明。"
          href={`/w/${workspaceId}/content-projects/${projectId}/assets`}
        />
        <ProjectArea
          icon={CalendarPlus}
          title="审核与排期"
          value={item.status === "review" ? "可以提交排期" : "尚未进入审核"}
          description="未审核内容不能生成可发布包。"
          href={`/w/${workspaceId}/schedule?project=${projectId}`}
        />
      </div>
      <section className="mt-5 rounded-xl border border-border bg-surface p-5">
        <h2 className="flex items-center gap-2 font-semibold">
          <FolderOpen size={17} /> 项目来源
        </h2>
        <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
          <div>
            <dt className="text-xs text-text-muted">来源选题</dt>
            <dd className="mt-1 font-mono text-xs">
              {item.topic_id || "直接创建"}
            </dd>
          </div>
          <div>
            <dt className="text-xs text-text-muted">负责人</dt>
            <dd className="mt-1">{item.owner_user_id || "未指派"}</dd>
          </div>
        </dl>
      </section>
      <EditProjectDialog
        workspaceId={workspaceId}
        project={item}
        open={editing}
        onClose={() => setEditing(false)}
      />
      <DeleteProjectDialog
        project={item}
        open={deleting}
        pending={remove.isPending}
        error={remove.error}
        onClose={() => setDeleting(false)}
        onConfirm={() =>
          remove.mutate(undefined, {
            onSuccess: () => router.push(`/w/${workspaceId}/content-projects`),
          })
        }
      />
    </>
  );
}

function ProjectArea({
  icon: Icon,
  title,
  value,
  description,
  href,
}: {
  icon: typeof FilePenLine;
  title: string;
  value: string;
  description: string;
  href: string;
}) {
  return (
    <Link
      className="group rounded-xl border border-border bg-surface p-5 shadow-panel"
      href={href}
    >
      <span className="grid size-10 place-items-center rounded-xl bg-primary-50 text-primary-600">
        <Icon size={18} />
      </span>
      <h2 className="mt-4 font-semibold">{title}</h2>
      <strong className="mt-2 block text-xl">{value}</strong>
      <p className="mt-2 text-xs leading-5 text-text-muted">{description}</p>
      <span className="mt-4 inline-flex items-center gap-1 text-xs font-medium text-primary-600">
        打开工作区 <ChevronRight size={14} />
      </span>
    </Link>
  );
}
