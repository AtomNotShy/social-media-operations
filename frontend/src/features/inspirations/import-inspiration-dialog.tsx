"use client";

import { CheckCircle2, Link2, LoaderCircle, X } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { useImportInspiration } from "@/src/features/inspirations/queries";

export function ImportInspirationDialog({
  workspaceId,
  open,
  onClose,
}: {
  workspaceId: string;
  open: boolean;
  onClose: () => void;
}) {
  const [url, setUrl] = useState("");
  const [analyze, setAnalyze] = useState(true);
  const mutation = useImportInspiration(workspaceId);

  if (!open) return null;

  const result = mutation.data;
  return (
    <div
      aria-labelledby="import-title"
      aria-modal="true"
      className="fixed inset-0 z-[70] flex justify-end bg-text/30 backdrop-blur-sm"
      role="dialog"
    >
      <button
        aria-label="关闭导入"
        className="absolute inset-0"
        onClick={onClose}
        type="button"
      />
      <section className="relative flex h-full w-full max-w-lg flex-col border-l border-border bg-surface p-6 shadow-popover sm:p-8">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-xs font-semibold tracking-[0.14em] text-primary-600 uppercase">
              Import URL
            </p>
            <h2 className="mt-1 text-xl font-semibold" id="import-title">
              从链接导入灵感
            </h2>
          </div>
          <button
            aria-label="关闭"
            className="grid size-9 place-items-center rounded-lg text-text-muted hover:bg-surface-subtle"
            onClick={onClose}
            type="button"
          >
            <X aria-hidden="true" size={18} />
          </button>
        </div>

        {result ? (
          <div className="mt-10">
            <span className="grid size-12 place-items-center rounded-xl bg-emerald-50 text-success">
              <CheckCircle2 aria-hidden="true" size={24} />
            </span>
            <h3 className="mt-5 text-lg font-semibold">
              {result.existing ? "内容已在灵感库中" : "导入任务已创建"}
            </h3>
            <p className="mt-2 text-sm leading-6 text-text-muted">
              {result.job_id
                ? "系统正在后台读取详情。任务创建不代表抓取或分析已经完成，请在任务中心查看真实进度。"
                : "内容记录已经返回，可以打开详情继续处理。"}
            </p>
            <div className="mt-6 flex flex-wrap gap-2">
              {result.inspiration_id ? (
                <Link
                  className="rounded-lg bg-primary-600 px-4 py-2.5 text-sm font-medium text-white"
                  href={`/w/${workspaceId}/inspirations/${result.inspiration_id}`}
                >
                  打开灵感
                </Link>
              ) : null}
              {result.job_id ? (
                <Link
                  className="rounded-lg border border-border px-4 py-2.5 text-sm font-medium hover:bg-surface-subtle"
                  href={`/w/${workspaceId}/jobs`}
                >
                  查看任务进度
                </Link>
              ) : null}
            </div>
          </div>
        ) : (
          <form
            className="mt-8"
            onSubmit={(event) => {
              event.preventDefault();
              mutation.mutate({ url: url.trim(), hydrate: "detail", analyze });
            }}
          >
            <label className="block">
              <span className="mb-2 block text-sm font-medium">公开内容链接</span>
              <div className="relative">
                <Link2
                  aria-hidden="true"
                  className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted"
                  size={16}
                />
                <input
                  autoFocus
                  className="h-11 w-full rounded-lg border border-border pl-10 pr-3 text-sm outline-none focus:border-primary-500"
                  onChange={(event) => setUrl(event.target.value)}
                  placeholder="https://..."
                  required
                  type="url"
                  value={url}
                />
              </div>
            </label>
            <label className="mt-5 flex items-start gap-3 rounded-xl border border-border bg-canvas/50 p-4">
              <input
                checked={analyze}
                className="mt-0.5 accent-blue-600"
                onChange={(event) => setAnalyze(event.target.checked)}
                type="checkbox"
              />
              <span>
                <span className="block text-sm font-medium">详情就绪后自动分析</span>
                <span className="mt-1 block text-xs leading-5 text-text-muted">
                  分析会以独立后台任务运行，结果和失败原因均可追踪。
                </span>
              </span>
            </label>

            {mutation.error ? (
              <p className="mt-5 rounded-lg border border-red-100 bg-red-50 px-3 py-2.5 text-xs text-red-700">
                {(mutation.error as { message?: string }).message ??
                  "导入请求失败，请检查链接后重试。"}
              </p>
            ) : null}

            <button
              className="mt-6 inline-flex w-full items-center justify-center gap-2 rounded-lg bg-primary-600 px-4 py-3 text-sm font-medium text-white hover:bg-primary-700 disabled:opacity-60"
              disabled={mutation.isPending || !url.trim()}
              type="submit"
            >
              {mutation.isPending ? (
                <LoaderCircle aria-hidden="true" className="animate-spin" size={16} />
              ) : (
                <Link2 aria-hidden="true" size={16} />
              )}
              {mutation.isPending ? "正在提交…" : "创建导入任务"}
            </button>
          </form>
        )}
      </section>
    </div>
  );
}
