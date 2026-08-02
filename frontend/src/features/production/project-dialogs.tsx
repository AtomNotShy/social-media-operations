"use client";

import { LoaderCircle, Trash2, X } from "lucide-react";
import { useState } from "react";
import { useUpdateProject } from "@/src/features/production/queries";
import type { ContentProject } from "@/src/features/production/types";
import {
  Dialog,
  InlineError,
  inputClass,
  primaryButton,
  secondaryButton,
} from "@/src/features/production/ui";

function toLocalInputValue(date: string) {
  const value = new Date(date);
  const pad = (part: number) => String(part).padStart(2, "0");
  return `${value.getFullYear()}-${pad(value.getMonth() + 1)}-${pad(value.getDate())}T${pad(value.getHours())}:${pad(value.getMinutes())}`;
}

export function EditProjectDialog({
  workspaceId,
  project,
  open,
  onClose,
}: {
  workspaceId: string;
  project: ContentProject | null;
  open: boolean;
  onClose: () => void;
}) {
  const update = useUpdateProject(workspaceId, project?.id ?? "");
  const [title, setTitle] = useState(project?.title ?? "");
  const [dueAt, setDueAt] = useState(
    project?.due_at ? toLocalInputValue(project.due_at) : "",
  );
  if (!open || !project) return null;
  return (
    <Dialog
      description="修改项目名称与截止时间；目标账号、来源选题和负责人由创建流程确定。"
      onClose={onClose}
      open={open}
      title="编辑内容项目"
    >
      <form
        className="grid gap-4"
        onSubmit={(event) => {
          event.preventDefault();
          update.mutate(
            {
              version: project.version,
              title: title.trim(),
              due_at: dueAt ? new Date(dueAt).toISOString() : null,
            },
            { onSuccess: onClose },
          );
        }}
      >
        <label className="text-sm font-medium">
          项目名称
          <input
            className={`${inputClass} mt-2`}
            required
            value={title}
            onChange={(event) => setTitle(event.target.value)}
          />
        </label>
        <label className="text-sm font-medium">
          截止时间
          <input
            className={`${inputClass} mt-2`}
            type="datetime-local"
            value={dueAt}
            onChange={(event) => setDueAt(event.target.value)}
          />
        </label>
        <InlineError error={update.error} />
        <div className="flex justify-end gap-2">
          <button
            className={secondaryButton}
            disabled={update.isPending}
            onClick={onClose}
            type="button"
          >
            取消
          </button>
          <button
            className={primaryButton}
            disabled={update.isPending}
            type="submit"
          >
            {update.isPending ? "正在保存…" : "保存修改"}
          </button>
        </div>
      </form>
    </Dialog>
  );
}

export function DeleteProjectDialog({
  project,
  open,
  error,
  pending,
  onClose,
  onConfirm,
}: {
  project: ContentProject | null;
  open: boolean;
  error?: unknown;
  pending: boolean;
  onClose: () => void;
  onConfirm: () => void;
}) {
  if (!open || !project) return null;
  return (
    <div
      aria-labelledby="delete-project-title"
      aria-modal="true"
      className="fixed inset-0 z-[80] grid place-items-center bg-text/30 p-4 backdrop-blur-sm"
      role="dialog"
    >
      <button
        aria-label="关闭删除确认"
        className="absolute inset-0"
        onClick={onClose}
        type="button"
      />
      <div className="relative w-full max-w-md rounded-2xl border border-border bg-surface p-6 shadow-popover">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs font-semibold tracking-[0.14em] text-danger uppercase">
              Remove project
            </p>
            <h2
              className="mt-1 text-xl font-semibold"
              id="delete-project-title"
            >
              删除内容项目？
            </h2>
          </div>
          <button
            aria-label="关闭"
            className="grid size-8 place-items-center rounded-lg text-text-muted hover:bg-surface-subtle"
            onClick={onClose}
            type="button"
          >
            <X aria-hidden="true" size={17} />
          </button>
        </div>
        <p className="mt-4 text-sm leading-6 text-text-muted">
          确认删除“{project.title}”？项目会从界面隐藏，脚本版本和素材一并移除；
          存在未完成排期时会阻止删除。
        </p>
        {error ? (
          <div className="mt-4 rounded-lg border border-red-100 bg-red-50 px-3 py-2.5 text-xs text-red-700">
            {(error as { message?: string }).message ?? "删除失败，请重试。"}
          </div>
        ) : null}
        <div className="mt-6 flex justify-end gap-2">
          <button
            className="rounded-lg border border-border px-4 py-2.5 text-sm font-medium hover:bg-surface-subtle"
            disabled={pending}
            onClick={onClose}
            type="button"
          >
            取消
          </button>
          <button
            className="inline-flex items-center gap-2 rounded-lg bg-danger px-4 py-2.5 text-sm font-medium text-white hover:bg-danger/90 disabled:cursor-not-allowed disabled:opacity-60"
            disabled={pending}
            onClick={onConfirm}
            type="button"
          >
            {pending ? (
              <LoaderCircle aria-hidden="true" className="animate-spin" size={15} />
            ) : (
              <Trash2 aria-hidden="true" size={15} />
            )}
            确认删除
          </button>
        </div>
      </div>
    </div>
  );
}
