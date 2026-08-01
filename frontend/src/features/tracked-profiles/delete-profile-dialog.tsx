import { LoaderCircle, Trash2, X } from "lucide-react";
import type { TrackedProfile } from "@/src/features/tracked-profiles/types";

export function DeleteProfileDialog({
  error,
  onClose,
  onConfirm,
  open,
  pending,
  profile,
}: {
  error?: unknown;
  onClose: () => void;
  onConfirm: () => void;
  open: boolean;
  pending: boolean;
  profile: Pick<TrackedProfile, "display_name"> | null;
}) {
  if (!open || !profile) return null;

  return (
    <div
      aria-labelledby="delete-profile-title"
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
              Remove profile
            </p>
            <h2 className="mt-1 text-xl font-semibold" id="delete-profile-title">
              删除对标账号？
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
          确认删除“{profile.display_name}”？账号会停止监控，历史采集内容会保留。
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
