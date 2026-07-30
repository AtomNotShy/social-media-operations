"use client";

import { BookmarkPlus, Check, LoaderCircle, X } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { useCreateSavedView, useSavedViews } from "@/src/features/production/queries";

export const primaryButton =
  "inline-flex min-h-10 items-center justify-center gap-2 rounded-lg bg-primary-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-primary-700 disabled:cursor-not-allowed disabled:opacity-50";
export const secondaryButton =
  "inline-flex min-h-10 items-center justify-center gap-2 rounded-lg border border-border bg-surface px-4 py-2 text-sm font-medium text-text transition hover:bg-surface-subtle disabled:cursor-not-allowed disabled:opacity-50";
export const inputClass =
  "min-h-11 w-full rounded-lg border border-border bg-surface px-3 text-sm outline-none placeholder:text-text-muted";
export const textareaClass =
  "min-h-28 w-full rounded-lg border border-border bg-surface p-3 text-sm leading-6 outline-none placeholder:text-text-muted";

export function MetricCard({
  label,
  value,
  helper,
}: {
  label: string;
  value: string | number;
  helper?: string;
}) {
  return (
    <div className="rounded-xl border border-border bg-surface p-4 shadow-panel">
      <p className="text-xs text-text-muted">{label}</p>
      <strong className="mt-2 block text-2xl font-semibold tabular-nums">{value}</strong>
      {helper ? <p className="mt-1 text-[11px] text-text-muted">{helper}</p> : null}
    </div>
  );
}

export function InlineError({ error }: { error: unknown }) {
  if (!error) return null;
  return (
    <p className="rounded-lg border border-red-100 bg-red-50 p-3 text-xs leading-5 text-red-700">
      {(error as { message?: string }).message ?? "操作没有完成，请重试。"}
    </p>
  );
}

export function SavedViewPicker({
  workspaceId,
  entityType,
}: {
  workspaceId: string;
  entityType:
    | "inspirations"
    | "tracked_profiles"
    | "topics"
    | "content_projects"
    | "publish_plans"
    | "reviews";
}) {
  const router = useRouter();
  const params = useSearchParams();
  const views = useSavedViews(workspaceId, entityType);
  const create = useCreateSavedView(workspaceId, entityType);
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");

  function apply(queryParams: Record<string, unknown>) {
    const next = new URLSearchParams();
    Object.entries(queryParams).forEach(([key, value]) => {
      if (typeof value === "string" && value) next.set(key, value);
    });
    router.replace(`?${next.toString()}`);
  }

  return (
    <div className="relative">
      <button className={secondaryButton} onClick={() => setOpen(!open)} type="button">
        <BookmarkPlus aria-hidden="true" size={15} />
        保存视图
      </button>
      {open ? (
        <div className="absolute right-0 top-12 z-30 w-72 rounded-xl border border-border bg-surface p-3 shadow-popover">
          <div className="mb-3 flex items-center justify-between">
            <p className="text-xs font-semibold">筛选视图</p>
            <button aria-label="关闭" onClick={() => setOpen(false)} type="button">
              <X size={15} />
            </button>
          </div>
          <div className="space-y-1">
            {views.data?.map((view) => (
              <button
                className="flex w-full items-center justify-between rounded-lg px-2.5 py-2 text-left text-xs hover:bg-surface-subtle"
                key={view.id}
                onClick={() => {
                  apply(view.query_params);
                  setOpen(false);
                }}
                type="button"
              >
                <span>{view.name}</span>
                {view.is_shared ? (
                  <span className="text-[10px] text-primary-600">团队</span>
                ) : null}
              </button>
            ))}
          </div>
          <div className="my-3 h-px bg-border" />
          <label className="text-[11px] font-medium text-text-muted">
            将当前筛选保存为
            <input
              className={`${inputClass} mt-1 min-h-9`}
              onChange={(event) => setName(event.target.value)}
              placeholder="例如：本周待审核"
              value={name}
            />
          </label>
          <button
            className={`${primaryButton} mt-2 w-full min-h-9`}
            disabled={!name.trim() || create.isPending}
            onClick={() =>
              create.mutate(
                {
                  entity_type: entityType,
                  name: name.trim(),
                  query_params: Object.fromEntries(params.entries()),
                  is_shared: false,
                },
                {
                  onSuccess: () => {
                    setName("");
                    setOpen(false);
                  },
                },
              )
            }
            type="button"
          >
            {create.isPending ? (
              <LoaderCircle className="animate-spin" size={14} />
            ) : (
              <Check size={14} />
            )}
            保存当前视图
          </button>
          <InlineError error={create.error} />
        </div>
      ) : null}
    </div>
  );
}

export function Dialog({
  open,
  title,
  description,
  onClose,
  children,
}: {
  open: boolean;
  title: string;
  description?: string;
  onClose: () => void;
  children: React.ReactNode;
}) {
  if (!open) return null;
  return (
    <div
      aria-modal="true"
      className="fixed inset-0 z-[70] grid place-items-center bg-text/35 p-4 backdrop-blur-sm"
      role="dialog"
    >
      <button aria-label="关闭" className="absolute inset-0" onClick={onClose} type="button" />
      <div className="relative max-h-[88vh] w-full max-w-xl overflow-y-auto rounded-2xl border border-border bg-surface p-6 shadow-popover">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-xl font-semibold">{title}</h2>
            {description ? (
              <p className="mt-1 text-sm leading-6 text-text-muted">{description}</p>
            ) : null}
          </div>
          <button
            aria-label="关闭"
            className="grid size-8 place-items-center rounded-lg hover:bg-surface-subtle"
            onClick={onClose}
            type="button"
          >
            <X aria-hidden="true" size={17} />
          </button>
        </div>
        <div className="mt-5">{children}</div>
      </div>
    </div>
  );
}

