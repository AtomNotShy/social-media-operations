"use client";

import {
  Grid2X2,
  LayoutList,
  Link2,
  Search,
} from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { EmptyState } from "@/src/components/ui/empty-state";
import { ErrorState } from "@/src/components/ui/error-state";
import { PageHeader } from "@/src/components/ui/page-header";
import { StatusBadge } from "@/src/components/ui/status-badge";
import { useWorkspaceRole } from "@/src/features/identity/queries";
import { ImportInspirationDialog } from "@/src/features/inspirations/import-inspiration-dialog";
import { InspirationCard } from "@/src/features/inspirations/inspiration-card";
import {
  contentTitle,
  inspirationStatusLabel,
} from "@/src/features/inspirations/presentation";
import { useInspirations } from "@/src/features/inspirations/queries";
import { formatRelativeTime, platformLabel } from "@/src/lib/format";

const statuses = [
  { label: "全部", value: undefined },
  { label: "待处理", value: "inbox" },
  { label: "已分析", value: "analyzed" },
  { label: "候选选题", value: "candidate" },
  { label: "已归档", value: "archived" },
];

const platforms = [
  { label: "全部平台", value: "" },
  { label: "小红书", value: "xiaohongshu" },
  { label: "抖音", value: "douyin" },
  { label: "哔哩哔哩", value: "bilibili" },
  { label: "YouTube", value: "youtube" },
  { label: "TikTok", value: "tiktok" },
  { label: "X", value: "x" },
];

export function InspirationsPage({ workspaceId }: { workspaceId: string }) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [queryInput, setQueryInput] = useState(searchParams.get("q") ?? "");
  const [importOpen, setImportOpen] = useState(
    searchParams.get("import") === "1",
  );
  const status = searchParams.get("status") ?? undefined;
  const platform = searchParams.get("platform") ?? undefined;
  const view = searchParams.get("view") === "list" ? "list" : "grid";
  const inspirations = useInspirations(workspaceId, {
    q: searchParams.get("q") ?? undefined,
    status,
    platform,
  });
  const permission = useWorkspaceRole(workspaceId);

  useEffect(() => {
    const timeout = window.setTimeout(() => {
      const params = new URLSearchParams(searchParams.toString());
      if (queryInput.trim()) params.set("q", queryInput.trim());
      else params.delete("q");
      params.delete("cursor");
      const suffix = params.toString();
      router.replace(
        `/w/${workspaceId}/inspirations${suffix ? `?${suffix}` : ""}`,
      );
    }, 350);
    return () => window.clearTimeout(timeout);
    // searchParams is intentionally included so external filters are preserved.
  }, [queryInput, router, searchParams, workspaceId]);

  const stats = useMemo(() => {
    const items = inspirations.data ?? [];
    return {
      total: items.length,
      ready: items.filter((item) => item.content.detail_status === "ready").length,
      analyzed: items.filter((item) => item.status === "analyzed").length,
      candidates: items.filter((item) => item.status === "candidate").length,
    };
  }, [inspirations.data]);

  function navigate(params: URLSearchParams) {
    const suffix = params.toString();
    router.replace(
      `/w/${workspaceId}/inspirations${suffix ? `?${suffix}` : ""}`,
    );
  }

  function setParam(key: string, value?: string) {
    const params = new URLSearchParams(searchParams.toString());
    if (value) params.set(key, value);
    else params.delete(key);
    params.delete("cursor");
    navigate(params);
  }

  return (
    <>
      <PageHeader
        eyebrow="研究与洞察"
        title="灵感库"
        description="沉淀公开内容、分析证据和可执行选题。导入、抓取、转写与分析状态均独立呈现。"
        actions={
          permission.canEdit ? (
            <button
              className="inline-flex items-center gap-2 rounded-lg bg-primary-600 px-4 py-2.5 text-sm font-medium text-white shadow-sm hover:bg-primary-700"
              onClick={() => setImportOpen(true)}
              type="button"
            >
              <Link2 aria-hidden="true" size={16} />
              导入内容链接
            </button>
          ) : (
            <span className="rounded-full border border-border bg-surface px-3 py-2 text-xs font-medium text-text-muted">
              Viewer · 只读
            </span>
          )
        }
      />

      <section className="mb-5 grid grid-cols-2 gap-3 xl:grid-cols-4">
        {[
          { label: "当前结果", value: stats.total, detail: "按当前筛选" },
          { label: "详情就绪", value: stats.ready, detail: "可继续处理" },
          { label: "已分析", value: stats.analyzed, detail: "有结构化结果" },
          { label: "候选选题", value: stats.candidates, detail: "等待进入生产" },
        ].map((item) => (
          <div
            className="rounded-xl border border-border bg-surface p-4 shadow-panel sm:p-5"
            key={item.label}
          >
            <p className="text-xs font-medium text-text-muted">{item.label}</p>
            <div className="mt-3 flex items-end justify-between gap-2">
              <strong className="text-2xl font-semibold tabular-nums">
                {item.value}
              </strong>
              <span className="text-[11px] text-text-muted">{item.detail}</span>
            </div>
          </div>
        ))}
      </section>

      <section className="mb-5 rounded-xl border border-border bg-surface p-3 shadow-panel">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
          <div className="relative min-w-0 flex-1">
            <Search
              aria-hidden="true"
              className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted"
              size={16}
            />
            <input
              aria-label="搜索灵感"
              className="h-10 w-full rounded-lg border border-border bg-canvas/60 pl-9 pr-3 text-sm outline-none focus:border-primary-500 focus:bg-surface"
              onChange={(event) => setQueryInput(event.target.value)}
              placeholder="搜索标题、正文、笔记或平台"
              value={queryInput}
            />
          </div>
          <select
            aria-label="按平台筛选"
            className="h-10 rounded-lg border border-border bg-surface px-3 text-sm outline-none focus:border-primary-500"
            onChange={(event) => setParam("platform", event.target.value)}
            value={platform ?? ""}
          >
            {platforms.map((item) => (
              <option key={item.label} value={item.value}>
                {item.label}
              </option>
            ))}
          </select>
          <div className="flex rounded-lg bg-surface-subtle p-1">
            <button
              aria-label="网格视图"
              className={`grid size-8 place-items-center rounded-md ${view === "grid" ? "bg-surface shadow-sm" : "text-text-muted"}`}
              onClick={() => setParam("view")}
              type="button"
            >
              <Grid2X2 aria-hidden="true" size={15} />
            </button>
            <button
              aria-label="列表视图"
              className={`grid size-8 place-items-center rounded-md ${view === "list" ? "bg-surface shadow-sm" : "text-text-muted"}`}
              onClick={() => setParam("view", "list")}
              type="button"
            >
              <LayoutList aria-hidden="true" size={16} />
            </button>
          </div>
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          {statuses.map((item) => (
            <button
              className={`rounded-full border px-3 py-1.5 text-xs font-medium ${
                status === item.value
                  ? "border-text bg-text text-white"
                  : "border-border text-text-muted hover:text-text"
              }`}
              key={item.label}
              onClick={() => setParam("status", item.value)}
              type="button"
            >
              {item.label}
            </button>
          ))}
        </div>
      </section>

      {inspirations.isLoading ? (
        <div
          aria-label="正在加载灵感"
          className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3"
        >
          {Array.from({ length: 6 }).map((_, index) => (
            <div
              className="h-80 animate-pulse rounded-xl bg-surface"
              key={index}
            />
          ))}
        </div>
      ) : inspirations.error ? (
        <section className="rounded-xl border border-border bg-surface">
          <ErrorState
            message={
              (inspirations.error as { message?: string }).message ??
              "灵感库暂时不可用。"
            }
            onRetry={() => inspirations.refetch()}
            requestId={(inspirations.error as { requestId?: string }).requestId}
          />
        </section>
      ) : inspirations.data?.length ? (
        view === "grid" ? (
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {inspirations.data.map((item) => (
              <InspirationCard
                href={`/w/${workspaceId}/inspirations/${item.id}`}
                item={item}
                key={item.id}
              />
            ))}
          </div>
        ) : (
          <section className="divide-y divide-border overflow-hidden rounded-xl border border-border bg-surface shadow-panel">
            {inspirations.data.map((item) => (
              <a
                className="grid gap-3 p-4 hover:bg-canvas/50 sm:grid-cols-[1fr_140px_120px_120px] sm:items-center"
                href={`/w/${workspaceId}/inspirations/${item.id}`}
                key={item.id}
              >
                <div className="min-w-0">
                  <h2 className="truncate text-sm font-semibold">
                    {contentTitle(item.content.title, item.content.body_text)}
                  </h2>
                  <p className="mt-1 truncate text-xs text-text-muted">
                    {item.content.body_text || "当前内容源未提供正文摘要。"}
                  </p>
                </div>
                <span className="text-xs text-text-muted">
                  {platformLabel(item.content.platform)}
                </span>
                <StatusBadge
                  label={inspirationStatusLabel(item.status)}
                  status={item.status === "archived" ? "paused" : item.status}
                />
                <span className="text-xs text-text-muted sm:text-right">
                  {formatRelativeTime(item.updated_at)}
                </span>
              </a>
            ))}
          </section>
        )
      ) : (
        <section className="rounded-xl border border-border bg-surface">
          <EmptyState
            action={
              permission.canEdit ? (
                <button
                  className="inline-flex items-center gap-2 rounded-lg bg-primary-600 px-4 py-2.5 text-sm font-medium text-white"
                  onClick={() => setImportOpen(true)}
                  type="button"
                >
                  <Link2 aria-hidden="true" size={16} />
                  导入第一条内容
                </button>
              ) : undefined
            }
            description="粘贴公开内容链接后，系统会创建可追踪的抓取任务。"
            title="还没有符合条件的灵感"
          />
        </section>
      )}

      <ImportInspirationDialog
        onClose={() => setImportOpen(false)}
        open={importOpen && permission.canEdit}
        workspaceId={workspaceId}
      />
    </>
  );
}
