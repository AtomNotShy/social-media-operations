"use client";

import {
  ArrowLeft,
  CheckCircle2,
  Save,
  ShieldAlert,
  ShieldCheck,
} from "lucide-react";
import Link from "next/link";
import { ErrorState } from "@/src/components/ui/error-state";
import { StatusBadge } from "@/src/components/ui/status-badge";
import { useWorkspaceRole } from "@/src/features/identity/queries";
import {
  evidenceValues,
  patternStatusLabel,
} from "@/src/features/patterns/presentation";
import {
  usePattern,
  useTransitionPattern,
  useUpdatePattern,
} from "@/src/features/patterns/queries";
import { formatRelativeTime, platformLabel } from "@/src/lib/format";

export function PatternDetailPage({
  workspaceId,
  patternId,
}: {
  workspaceId: string;
  patternId: string;
}) {
  const pattern = usePattern(workspaceId, patternId);
  const permission = useWorkspaceRole(workspaceId);
  const update = useUpdatePattern(workspaceId, patternId);
  const transition = useTransitionPattern(workspaceId, patternId);

  if (pattern.isLoading) {
    return <div aria-label="正在加载模式详情" className="h-96 animate-pulse rounded-xl bg-surface" />;
  }
  if (pattern.error || !pattern.data) {
    return (
      <section className="rounded-xl border border-border bg-surface">
        <ErrorState
          message={(pattern.error as { message?: string })?.message ?? "没有找到这个模式。"}
          onRetry={() => pattern.refetch()}
          requestId={(pattern.error as { requestId?: string })?.requestId}
        />
      </section>
    );
  }

  const item = pattern.data;
  const evidence = evidenceValues(item.evidence);

  return (
    <>
      <Link
        className="mb-5 inline-flex items-center gap-2 text-xs font-medium text-text-muted hover:text-text"
        href={`/w/${workspaceId}/patterns`}
      >
        <ArrowLeft aria-hidden="true" size={14} />
        返回可复用模式
      </Link>

      <section className="mb-5 rounded-2xl border border-border bg-surface p-6 shadow-panel sm:p-8">
        <div className="flex flex-wrap items-start justify-between gap-5">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold tracking-[0.14em] text-primary-600 uppercase">
                {item.pattern_type}
              </span>
              <StatusBadge label={patternStatusLabel(item.status)} status={item.status} />
            </div>
            <h1 className="mt-3 text-3xl font-semibold tracking-tight">{item.name}</h1>
            <p className="mt-3 max-w-3xl text-sm leading-7 text-text-muted">
              {item.description}
            </p>
          </div>
          {permission.canEdit ? (
            <div className="flex gap-2">
              {item.status === "draft" ? (
                <button
                  className="inline-flex items-center gap-2 rounded-lg bg-primary-600 px-4 py-2.5 text-sm font-medium text-white disabled:opacity-50"
                  disabled={transition.isPending}
                  onClick={() => transition.mutate("validated")}
                  type="button"
                >
                  <CheckCircle2 aria-hidden="true" size={16} />
                  标记已验证
                </button>
              ) : item.status === "validated" ? (
                <button
                  className="inline-flex items-center gap-2 rounded-lg border border-border px-4 py-2.5 text-sm font-medium disabled:opacity-50"
                  disabled={transition.isPending}
                  onClick={() => transition.mutate("retired")}
                  type="button"
                >
                  <ShieldAlert aria-hidden="true" size={16} />
                  退役模式
                </button>
              ) : null}
            </div>
          ) : null}
        </div>
      </section>

      <div className="grid gap-5 xl:grid-cols-[1fr_0.7fr]">
        <section className="rounded-xl border border-border bg-surface p-5 shadow-panel sm:p-6">
          <h2 className="font-semibold">证据与适用边界</h2>
          <div className="mt-5 grid grid-cols-2 gap-3">
            <EvidenceCard label="成功次数" value={String(evidence.success)} positive />
            <EvidenceCard label="失败次数" value={String(evidence.failure)} />
          </div>
          <div className="mt-5 rounded-xl border border-amber-100 bg-amber-50 p-4">
            <p className="text-xs font-semibold text-amber-900">不适用条件</p>
            <p className="mt-2 text-sm leading-6 text-amber-800">{evidence.limitations}</p>
          </div>
          <div className="mt-5">
            <p className="text-xs text-text-muted">来源内容</p>
            {item.source_content_ids.length ? (
              <div className="mt-2 flex flex-wrap gap-2">
                {item.source_content_ids.map((id) => (
                  <span className="rounded-lg bg-canvas px-2.5 py-1.5 font-mono text-[10px]" key={String(id)}>
                    {String(id).slice(0, 12)}
                  </span>
                ))}
              </div>
            ) : (
              <p className="mt-2 text-sm text-text-muted">尚未关联来源内容。</p>
            )}
          </div>
          <div className="mt-5">
            <p className="text-xs text-text-muted">适用平台</p>
            <div className="mt-2 flex flex-wrap gap-2">
              {item.applicable_channels.length
                ? item.applicable_channels.map((channel) => (
                    <span className="rounded-full border border-border px-3 py-1 text-xs" key={String(channel)}>
                      {platformLabel(String(channel))}
                    </span>
                  ))
                : <span className="text-sm text-text-muted">尚未限定</span>}
            </div>
          </div>
        </section>

        <section className="rounded-xl border border-border bg-surface p-5 shadow-panel sm:p-6">
          <div className="flex items-center gap-3">
            <span className="grid size-9 place-items-center rounded-lg bg-primary-50 text-primary-600">
              <ShieldCheck aria-hidden="true" size={17} />
            </span>
            <div>
              <h2 className="font-semibold">模式维护</h2>
              <p className="text-xs text-text-muted">更新于 {formatRelativeTime(item.updated_at)}</p>
            </div>
          </div>
          {permission.canEdit ? (
            <form
              className="mt-5 space-y-4"
              key={item.updated_at}
              onSubmit={(event) => {
                event.preventDefault();
                const data = new FormData(event.currentTarget);
                update.mutate({
                  name: String(data.get("name") ?? ""),
                  description: String(data.get("description") ?? ""),
                  evidence: {
                    ...item.evidence,
                    limitations: String(data.get("limitations") ?? ""),
                  },
                });
              }}
            >
              <label className="block">
                <span className="mb-2 block text-xs font-medium text-text-muted">名称</span>
                <input
                  className="h-10 w-full rounded-lg border border-border px-3 text-sm"
                  defaultValue={item.name}
                  name="name"
                  required
                />
              </label>
              <label className="block">
                <span className="mb-2 block text-xs font-medium text-text-muted">描述</span>
                <textarea
                  className="min-h-28 w-full rounded-lg border border-border p-3 text-sm leading-6"
                  defaultValue={item.description}
                  name="description"
                  required
                />
              </label>
              <label className="block">
                <span className="mb-2 block text-xs font-medium text-text-muted">不适用条件</span>
                <textarea
                  className="min-h-24 w-full rounded-lg border border-border p-3 text-sm leading-6"
                  defaultValue={evidence.limitations}
                  name="limitations"
                />
              </label>
              <button
                className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-primary-600 px-4 py-2.5 text-sm font-medium text-white disabled:opacity-50"
                disabled={update.isPending}
                type="submit"
              >
                <Save aria-hidden="true" size={15} />
                保存修改
              </button>
            </form>
          ) : (
            <p className="mt-5 rounded-lg bg-canvas p-4 text-sm text-text-muted">
              Viewer 可查看证据，但不能修改或变更模式状态。
            </p>
          )}
        </section>
      </div>
    </>
  );
}

function EvidenceCard({
  label,
  value,
  positive,
}: {
  label: string;
  value: string;
  positive?: boolean;
}) {
  return (
    <div className={`rounded-xl p-4 ${positive ? "bg-emerald-50" : "bg-red-50"}`}>
      <p className="text-xs text-text-muted">{label}</p>
      <strong className="mt-2 block text-2xl font-semibold tabular-nums">{value}</strong>
    </div>
  );
}
