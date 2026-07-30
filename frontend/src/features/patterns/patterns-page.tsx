"use client";

import { ArrowUpRight, Plus, Shapes, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { EmptyState } from "@/src/components/ui/empty-state";
import { ErrorState } from "@/src/components/ui/error-state";
import { PageHeader } from "@/src/components/ui/page-header";
import { StatusBadge } from "@/src/components/ui/status-badge";
import { useWorkspaceRole } from "@/src/features/identity/queries";
import {
  evidenceValues,
  patternStatusLabel,
} from "@/src/features/patterns/presentation";
import { useCreatePattern, usePatterns } from "@/src/features/patterns/queries";
import type { PatternCreate } from "@/src/features/patterns/types";
import { formatRelativeTime } from "@/src/lib/format";

const statuses = [
  { label: "全部", value: undefined },
  { label: "草稿", value: "draft" },
  { label: "已验证", value: "validated" },
  { label: "已退役", value: "retired" },
];

export function PatternsPage({ workspaceId }: { workspaceId: string }) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const status = searchParams.get("status") ?? undefined;
  const patterns = usePatterns(workspaceId, status);
  const permission = useWorkspaceRole(workspaceId);
  const [createOpen, setCreateOpen] = useState(false);

  function setStatus(value?: string) {
    const params = new URLSearchParams();
    if (value) params.set("status", value);
    const suffix = params.toString();
    router.replace(`/w/${workspaceId}/patterns${suffix ? `?${suffix}` : ""}`);
  }

  const validated =
    patterns.data?.filter((item) => item.status === "validated").length ?? 0;

  return (
    <>
      <PageHeader
        eyebrow="研究与洞察"
        title="可复用模式"
        description="把分析结果沉淀成经过证据验证的钩子、结构和表达方式，并保留不适用条件。"
        actions={
          permission.canEdit ? (
            <button
              className="inline-flex items-center gap-2 rounded-lg bg-primary-600 px-4 py-2.5 text-sm font-medium text-white"
              onClick={() => setCreateOpen(true)}
              type="button"
            >
              <Plus aria-hidden="true" size={16} />
              新建模式
            </button>
          ) : null
        }
      />

      <section className="mb-5 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Metric label="当前结果" value={patterns.data?.length ?? 0} />
        <Metric label="已验证" value={validated} />
        <Metric
          label="草稿"
          value={patterns.data?.filter((item) => item.status === "draft").length ?? 0}
        />
        <Metric
          label="已退役"
          value={patterns.data?.filter((item) => item.status === "retired").length ?? 0}
        />
      </section>

      <div className="mb-4 flex flex-wrap gap-2">
        {statuses.map((item) => (
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

      {patterns.isLoading ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 6 }).map((_, index) => (
            <div className="h-56 animate-pulse rounded-xl bg-surface" key={index} />
          ))}
        </div>
      ) : patterns.error ? (
        <section className="rounded-xl border border-border bg-surface">
          <ErrorState
            message={
              (patterns.error as { message?: string }).message ??
              "可复用模式暂时不可用。"
            }
            onRetry={() => patterns.refetch()}
            requestId={(patterns.error as { requestId?: string }).requestId}
          />
        </section>
      ) : patterns.data?.length ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {patterns.data.map((pattern) => {
            const evidence = evidenceValues(pattern.evidence);
            return (
              <Link
                className="group rounded-xl border border-border bg-surface p-5 shadow-panel transition hover:-translate-y-0.5 hover:shadow-popover"
                href={`/w/${workspaceId}/patterns/${pattern.id}`}
                key={pattern.id}
              >
                <div className="flex items-start justify-between gap-3">
                  <span className="grid size-10 place-items-center rounded-xl bg-primary-50 text-primary-600">
                    <Shapes aria-hidden="true" size={19} />
                  </span>
                  <StatusBadge
                    label={patternStatusLabel(pattern.status)}
                    status={pattern.status}
                  />
                </div>
                <p className="mt-5 text-[10px] font-semibold tracking-[0.14em] text-primary-600 uppercase">
                  {pattern.pattern_type}
                </p>
                <h2 className="mt-1 flex items-center justify-between gap-2 text-base font-semibold">
                  <span>{pattern.name}</span>
                  <ArrowUpRight
                    aria-hidden="true"
                    className="shrink-0 text-text-muted transition group-hover:-translate-y-0.5 group-hover:translate-x-0.5"
                    size={16}
                  />
                </h2>
                <p className="mt-2 line-clamp-3 min-h-16 text-sm leading-6 text-text-muted">
                  {pattern.description}
                </p>
                <div className="mt-5 flex items-center justify-between border-t border-border pt-4 text-xs text-text-muted">
                  <span className="inline-flex items-center gap-1">
                    <ShieldCheck aria-hidden="true" size={14} />
                    成功 {evidence.success} · 失败 {evidence.failure}
                  </span>
                  <span>{formatRelativeTime(pattern.updated_at)}</span>
                </div>
              </Link>
            );
          })}
        </div>
      ) : (
        <section className="rounded-xl border border-border bg-surface">
          <EmptyState
            action={
              permission.canEdit ? (
                <button
                  className="rounded-lg bg-primary-600 px-4 py-2.5 text-sm font-medium text-white"
                  onClick={() => setCreateOpen(true)}
                  type="button"
                >
                  创建第一个模式
                </button>
              ) : undefined
            }
            description="从成功的 L1/L2 分析提炼，或手工记录一个待验证模式。"
            title="还没有符合条件的模式"
          />
        </section>
      )}

      <CreatePatternDialog
        onClose={() => setCreateOpen(false)}
        open={createOpen && permission.canEdit}
        workspaceId={workspaceId}
      />
    </>
  );
}

function CreatePatternDialog({
  workspaceId,
  open,
  onClose,
}: {
  workspaceId: string;
  open: boolean;
  onClose: () => void;
}) {
  const create = useCreatePattern(workspaceId);
  const [values, setValues] = useState<PatternCreate>({
    name: "",
    description: "",
    pattern_type: "hook",
    applicable_channels: [],
    source_content_ids: [],
    evidence: {},
  });
  if (!open) return null;

  return (
    <div
      aria-modal="true"
      className="fixed inset-0 z-[70] grid place-items-center bg-text/30 p-4 backdrop-blur-sm"
      role="dialog"
    >
      <button aria-label="关闭" className="absolute inset-0" onClick={onClose} type="button" />
      <form
        className="relative w-full max-w-lg rounded-2xl border border-border bg-surface p-6 shadow-popover"
        onSubmit={(event) => {
          event.preventDefault();
          create.mutate(values, { onSuccess: onClose });
        }}
      >
        <p className="text-xs font-semibold tracking-[0.14em] text-primary-600 uppercase">
          New pattern
        </p>
        <h2 className="mt-1 text-xl font-semibold">新建可复用模式</h2>
        <div className="mt-6 grid gap-4">
          <label>
            <span className="mb-2 block text-sm font-medium">名称</span>
            <input
              className="h-11 w-full rounded-lg border border-border px-3 text-sm"
              maxLength={255}
              onChange={(event) => setValues({ ...values, name: event.target.value })}
              required
              value={values.name}
            />
          </label>
          <label>
            <span className="mb-2 block text-sm font-medium">类型</span>
            <select
              className="h-11 w-full rounded-lg border border-border bg-surface px-3 text-sm"
              onChange={(event) =>
                setValues({ ...values, pattern_type: event.target.value })
              }
              value={values.pattern_type}
            >
              <option value="hook">钩子</option>
              <option value="structure">结构</option>
              <option value="topic">选题</option>
              <option value="expression">表达</option>
            </select>
          </label>
          <label>
            <span className="mb-2 block text-sm font-medium">描述</span>
            <textarea
              className="min-h-28 w-full rounded-lg border border-border p-3 text-sm leading-6"
              onChange={(event) =>
                setValues({ ...values, description: event.target.value })
              }
              required
              value={values.description}
            />
          </label>
        </div>
        {create.error ? (
          <p className="mt-4 rounded-lg bg-red-50 p-3 text-xs text-red-700">
            {(create.error as { message?: string }).message ?? "创建失败。"}
          </p>
        ) : null}
        <div className="mt-6 flex justify-end gap-2">
          <button
            className="rounded-lg border border-border px-4 py-2.5 text-sm font-medium"
            onClick={onClose}
            type="button"
          >
            取消
          </button>
          <button
            className="rounded-lg bg-primary-600 px-4 py-2.5 text-sm font-medium text-white disabled:opacity-50"
            disabled={create.isPending}
            type="submit"
          >
            创建草稿
          </button>
        </div>
      </form>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-xl border border-border bg-surface p-4 shadow-panel">
      <p className="text-xs text-text-muted">{label}</p>
      <strong className="mt-2 block text-2xl font-semibold tabular-nums">{value}</strong>
    </div>
  );
}
