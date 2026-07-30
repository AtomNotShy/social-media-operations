"use client";

import {
  AlertCircle,
  Ban,
  CheckCircle2,
  Clock3,
  LoaderCircle,
  RotateCcw,
  TerminalSquare,
} from "lucide-react";
import { useSearchParams, useRouter } from "next/navigation";
import { ErrorState } from "@/src/components/ui/error-state";
import { PageHeader } from "@/src/components/ui/page-header";
import { StatusBadge } from "@/src/components/ui/status-badge";
import { useJobAction, useJobs } from "@/src/features/jobs/queries";
import { useWorkspaceRole } from "@/src/features/identity/queries";
import type { Job } from "@/src/features/tracked-profiles/types";
import {
  formatRelativeTime,
  jobStatusLabel,
} from "@/src/lib/format";

const filters = [
  { label: "全部任务", value: undefined },
  { label: "进行中", value: "running" },
  { label: "等待中", value: "pending" },
  { label: "失败", value: "failed" },
  { label: "已完成", value: "succeeded" },
];

export function JobsPage({ workspaceId }: { workspaceId: string }) {
  const searchParams = useSearchParams();
  const router = useRouter();
  const status = searchParams.get("status") ?? undefined;
  const jobs = useJobs(workspaceId, status);
  const action = useJobAction(workspaceId);
  const permission = useWorkspaceRole(workspaceId);

  function setStatus(next?: string) {
    const params = new URLSearchParams(searchParams.toString());
    if (next) params.set("status", next);
    else params.delete("status");
    const suffix = params.toString();
    router.replace(`/w/${workspaceId}/jobs${suffix ? `?${suffix}` : ""}`);
  }

  return (
    <>
      <PageHeader
        eyebrow="系统"
        title="任务中心"
        description="所有数据采集与分析任务都在这里留下状态和失败原因；页面不会把“已创建”显示成“已完成”。"
      />

      <div className="mb-4 flex flex-wrap items-center gap-2">
        {filters.map((item) => (
          <button
            className={`rounded-full border px-3.5 py-2 text-xs font-medium ${
              status === item.value
                ? "border-text bg-text text-white"
                : "border-border bg-surface text-text-muted hover:text-text"
            }`}
            key={item.label}
            onClick={() => setStatus(item.value)}
            type="button"
          >
            {item.label}
          </button>
        ))}
      </div>

      <section className="overflow-hidden rounded-xl border border-border bg-surface shadow-panel">
        <div className="grid grid-cols-[1fr_auto] items-center border-b border-border bg-canvas/60 px-5 py-3 text-xs text-text-muted sm:grid-cols-[1fr_140px_140px_120px]">
          <span>任务</span>
          <span className="hidden sm:block">创建时间</span>
          <span className="hidden sm:block">状态</span>
          <span className="text-right">操作</span>
        </div>

        {jobs.isLoading ? (
          <div className="divide-y divide-border">
            {Array.from({ length: 4 }).map((_, index) => (
              <div className="flex animate-pulse items-center gap-4 p-5" key={index}>
                <div className="size-10 rounded-lg bg-surface-subtle" />
                <div className="flex-1 space-y-2">
                  <div className="h-3 w-36 rounded bg-surface-subtle" />
                  <div className="h-2.5 w-56 rounded bg-surface-subtle" />
                </div>
              </div>
            ))}
          </div>
        ) : jobs.error ? (
          <ErrorState
            message={
              (jobs.error as { message?: string }).message ??
              "任务列表暂时不可用。"
            }
            onRetry={() => jobs.refetch()}
            requestId={(jobs.error as { requestId?: string }).requestId}
          />
        ) : jobs.data?.length ? (
          <div className="divide-y divide-border">
            {jobs.data.map((job) => (
              <JobRow
                busy={action.isPending && action.variables?.job.id === job.id}
                canEdit={permission.canEdit}
                job={job}
                key={job.id}
                onAction={(nextAction) =>
                  action.mutate({ job, action: nextAction })
                }
              />
            ))}
          </div>
        ) : (
          <div className="flex min-h-64 flex-col items-center justify-center px-6 text-center">
            <CheckCircle2
              aria-hidden="true"
              className="mb-4 text-success"
              size={28}
            />
            <h2 className="font-semibold">没有符合条件的任务</h2>
            <p className="mt-2 text-sm text-text-muted">
              发起账号同步后，任务会立即出现在这里。
            </p>
          </div>
        )}
      </section>
    </>
  );
}

function JobRow({
  job,
  onAction,
  busy,
  canEdit,
}: {
  job: Job;
  onAction: (action: "retry" | "cancel") => void;
  busy: boolean;
  canEdit: boolean;
}) {
  const icon = {
    running: LoaderCircle,
    pending: Clock3,
    retry_wait: Clock3,
    succeeded: CheckCircle2,
    failed: AlertCircle,
    dead: AlertCircle,
    cancelled: Ban,
  }[job.status] ?? TerminalSquare;
  const Icon = icon;
  const canRetry = ["failed", "dead"].includes(job.status);
  const canCancel = ["pending", "retry_wait"].includes(job.status);

  return (
    <article className="grid grid-cols-[1fr_auto] items-center gap-4 px-5 py-4 sm:grid-cols-[1fr_140px_140px_120px]">
      <div className="flex min-w-0 items-start gap-3">
        <span
          className={`mt-0.5 grid size-9 shrink-0 place-items-center rounded-lg ${
            ["failed", "dead"].includes(job.status)
              ? "bg-red-50 text-danger"
              : job.status === "succeeded"
                ? "bg-emerald-50 text-success"
                : "bg-primary-50 text-primary-600"
          }`}
        >
          <Icon
            aria-hidden="true"
            className={job.status === "running" ? "animate-spin" : ""}
            size={17}
          />
        </span>
        <div className="min-w-0">
          <h2 className="truncate text-sm font-medium">
            {jobTypeLabel(job.job_type)}
          </h2>
          <p className="mt-1 truncate text-xs text-text-muted">
            ID {job.id.slice(0, 8)} · 尝试 {job.attempt}/{job.max_attempts}
          </p>
          {job.last_error_message ? (
            <p className="mt-2 line-clamp-2 text-xs leading-5 text-danger">
              {job.last_error_message}
            </p>
          ) : null}
          <div className="mt-2 sm:hidden">
            <StatusBadge
              label={jobStatusLabel(job.status)}
              status={job.status}
            />
          </div>
        </div>
      </div>
      <span className="hidden text-xs text-text-muted sm:block">
        {formatRelativeTime(job.created_at)}
      </span>
      <span className="hidden sm:block">
        <StatusBadge label={jobStatusLabel(job.status)} status={job.status} />
      </span>
      <div className="flex justify-end">
        {!canEdit ? (
          <span className="text-xs text-text-muted">只读</span>
        ) : canRetry ? (
          <button
            className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-2 text-xs font-medium hover:bg-surface-subtle disabled:opacity-50"
            disabled={busy}
            onClick={() => onAction("retry")}
            type="button"
          >
            <RotateCcw aria-hidden="true" size={14} />
            重试
          </button>
        ) : canCancel ? (
          <button
            className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-2 text-xs font-medium hover:bg-surface-subtle disabled:opacity-50"
            disabled={busy}
            onClick={() => onAction("cancel")}
            type="button"
          >
            <Ban aria-hidden="true" size={14} />
            取消
          </button>
        ) : (
          <span className="text-xs text-text-muted">—</span>
        )}
      </div>
    </article>
  );
}

function jobTypeLabel(type: string) {
  return (
    {
      PROFILE_SCAN: "对标账号同步",
      CONTENT_IMPORT: "内容导入",
      TRANSCRIPTION: "内容转写",
      ANALYSIS: "AI 内容分析",
    }[type] ?? type
  );
}
