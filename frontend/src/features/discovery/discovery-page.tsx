"use client";

import {
  CheckCircle2,
  Compass,
  ExternalLink,
  LoaderCircle,
  Search,
  Sparkles,
} from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { EmptyState } from "@/src/components/ui/empty-state";
import { ErrorState } from "@/src/components/ui/error-state";
import { PageHeader } from "@/src/components/ui/page-header";
import { StatusBadge } from "@/src/components/ui/status-badge";
import {
  useCreateDiscoverySearch,
  useDiscoverySearch,
  useDiscoverySearchEstimate,
  useImportDiscoveryResults,
} from "@/src/features/discovery/queries";
import type { DiscoveryResult } from "@/src/features/discovery/types";
import { useWorkspaceRole } from "@/src/features/identity/queries";
import { formatCompactNumber, platformLabel } from "@/src/lib/format";

export function DiscoveryPage({ workspaceId }: { workspaceId: string }) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const jobId = searchParams.get("job") ?? undefined;
  const [query, setQuery] = useState(searchParams.get("q") ?? "");
  const [maxPages, setMaxPages] = useState(1);
  const [sortType, setSortType] = useState<
    "general" | "time_descending" | "popularity_descending" | "comment_descending" | "collect_descending"
  >("popularity_descending");
  const [confirming, setConfirming] = useState(false);
  const [selected, setSelected] = useState<string[]>([]);
  const permission = useWorkspaceRole(workspaceId);
  const create = useCreateDiscoverySearch(workspaceId);
  const search = useDiscoverySearch(workspaceId, jobId);
  const estimate = useDiscoverySearchEstimate(
    workspaceId,
    search.data?.max_pages ?? maxPages,
  );
  const importer = useImportDiscoveryResults(workspaceId, jobId);

  const results = search.data?.results ?? [];
  const freshResults = results.filter((item) => !item.imported_external_content_id);
  const allFreshSelected =
    freshResults.length > 0 &&
    freshResults.every((item) => selected.includes(item.id));

  const metrics = {
    total: results.length,
    new: freshResults.length,
    imported: results.filter((item) => item.imported_external_content_id).length,
  };

  function startSearch() {
    create.mutate(
      {
        platform: "xiaohongshu",
        query: query.trim(),
        max_pages: maxPages,
        hydrate_top: 0,
        sort_type: sortType,
        note_type: "不限",
        time_filter: "一周内",
      },
      {
        onSuccess: (accepted) => {
          setConfirming(false);
          setSelected([]);
          const params = new URLSearchParams();
          params.set("q", query.trim());
          params.set("job", accepted.job_id);
          router.replace(`/w/${workspaceId}/discover?${params}`);
        },
      },
    );
  }

  return (
    <>
      <PageHeader
        eyebrow="研究与洞察"
        title="搜索与热榜"
        description="主动寻找尚未入库的公开内容；选择“热度优先”即可查看当前关键词热榜，确认后才导入详情。"
        actions={
          <Link
            className="rounded-lg border border-border bg-surface px-4 py-2.5 text-sm font-medium hover:bg-surface-subtle"
            href={`/w/${workspaceId}/inspirations`}
          >
            返回灵感库
          </Link>
        }
      />

      <div className="grid gap-5 xl:grid-cols-[360px_1fr]">
        <aside className="self-start rounded-xl border border-border bg-surface p-5 shadow-panel xl:sticky xl:top-24">
          <div className="flex items-center gap-3">
            <span className="grid size-10 place-items-center rounded-xl bg-primary-50 text-primary-600">
              <Compass aria-hidden="true" size={19} />
            </span>
            <div>
              <h2 className="font-semibold">创建搜索任务</h2>
              <p className="mt-0.5 text-xs text-text-muted">当前契约支持小红书</p>
            </div>
          </div>
          <form
            className="mt-6 space-y-4"
            onSubmit={(event) => {
              event.preventDefault();
              setConfirming(true);
            }}
          >
            <label className="block">
              <span className="mb-2 block text-xs font-medium text-text-muted">
                关键词
              </span>
              <div className="relative">
                <Search
                  aria-hidden="true"
                  className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted"
                  size={15}
                />
                <input
                  className="h-10 w-full rounded-lg border border-border pl-9 pr-3 text-sm outline-none focus:border-primary-500"
                  maxLength={100}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="例如：餐饮运营"
                  required
                  value={query}
                />
              </div>
            </label>
            <div className="grid grid-cols-1 gap-3">
              <label>
                <span className="mb-2 block text-xs font-medium text-text-muted">
                  搜索页数
                </span>
                <select
                  className="h-10 w-full rounded-lg border border-border bg-surface px-3 text-sm"
                  onChange={(event) => setMaxPages(Number(event.target.value))}
                  value={maxPages}
                >
                  {[1, 2, 3, 4, 5].map((value) => (
                    <option key={value} value={value}>
                      {value} 页
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <label className="block">
              <span className="mb-2 block text-xs font-medium text-text-muted">
                排序
              </span>
              <select
                className="h-10 w-full rounded-lg border border-border bg-surface px-3 text-sm"
                onChange={(event) =>
                  setSortType(event.target.value as typeof sortType)
                }
                value={sortType}
              >
                <option value="general">综合</option>
                <option value="popularity_descending">热度优先</option>
                <option value="time_descending">最新优先</option>
                <option value="comment_descending">评论优先</option>
                <option value="collect_descending">收藏优先</option>
              </select>
            </label>

            <div className="rounded-lg bg-canvas/70 p-3 text-xs leading-5 text-text-muted">
              服务端预估：{estimate.data?.provider_calls ?? maxPages} 次供应商调用，
              费用 US${estimate.data?.estimated_provider_cost_usd ?? "—"}。
              搜索只读取摘要；选择导入后才创建详情增强任务。
            </div>

            {confirming ? (
              <div className="rounded-xl border border-amber-200 bg-amber-50 p-4">
                <p className="text-sm font-semibold text-amber-900">确认产生外部调用？</p>
                <p className="mt-1 text-xs leading-5 text-amber-800">
                  这会创建 1 个搜索任务，读取 {maxPages} 页，并受工作区预算限制。
                </p>
                <div className="mt-3 flex gap-2">
                  <button
                    className="rounded-lg bg-text px-3 py-2 text-xs font-medium text-white disabled:opacity-50"
                    disabled={create.isPending}
                    onClick={startSearch}
                    type="button"
                  >
                    {create.isPending ? "正在创建…" : "确认创建"}
                  </button>
                  <button
                    className="rounded-lg border border-amber-200 px-3 py-2 text-xs font-medium"
                    onClick={() => setConfirming(false)}
                    type="button"
                  >
                    取消
                  </button>
                </div>
              </div>
            ) : (
              <button
                className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-primary-600 px-4 py-2.5 text-sm font-medium text-white disabled:opacity-50"
                disabled={!permission.canEdit || !query.trim()}
                type="submit"
              >
                <Search aria-hidden="true" size={16} />
                创建搜索任务
              </button>
            )}
            {!permission.canEdit ? (
              <p className="text-xs text-text-muted">Viewer 可以查看结果，但不能创建付费任务。</p>
            ) : null}
            {create.error ? (
              <p className="rounded-lg bg-red-50 p-3 text-xs text-red-700">
                {(create.error as { message?: string }).message ?? "搜索任务创建失败。"}
              </p>
            ) : null}
          </form>
        </aside>

        <main className="min-w-0">
          {!jobId ? (
            <section className="rounded-xl border border-border bg-surface">
              <EmptyState
                description="设置关键词和调用范围后创建任务。搜索结果与灵感库分开，只有选中导入的内容才会入库。"
                title="开始一次主动发现"
              />
            </section>
          ) : search.isLoading ? (
            <section className="grid min-h-80 place-items-center rounded-xl border border-border bg-surface">
              <div className="text-center">
                <LoaderCircle
                  aria-hidden="true"
                  className="mx-auto animate-spin text-primary-600"
                  size={28}
                />
                <p className="mt-3 text-sm font-medium">正在读取搜索任务…</p>
              </div>
            </section>
          ) : search.error ? (
            <section className="rounded-xl border border-border bg-surface">
              <ErrorState
                message={
                  (search.error as { message?: string }).message ??
                  "搜索结果暂时不可用；历史灵感不受影响。"
                }
                onRetry={() => search.refetch()}
                requestId={(search.error as { requestId?: string }).requestId}
              />
            </section>
          ) : search.data ? (
            <>
              <section className="mb-4 rounded-xl border border-border bg-surface p-5 shadow-panel">
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div>
                    <div className="flex items-center gap-2">
                      <h2 className="text-lg font-semibold">“{search.data.query}”</h2>
                      <StatusBadge
                        label={searchStatusLabel(search.data.status)}
                        status={search.data.status}
                      />
                    </div>
                    <p className="mt-1 text-xs text-text-muted">
                      {platformLabel(search.data.platform)} · {search.data.max_pages} 页 ·
                      摘要结果按 {sortLabel(search.data.parameters.sort_type)} 排序 ·
                      刷新于{" "}
                      {new Date(
                        search.data.finished_at ?? search.data.created_at,
                      ).toLocaleString("zh-CN")}
                    </p>
                  </div>
                  <div className="rounded-lg bg-primary-50 px-3 py-2 text-xs text-primary-700">
                    服务端预估费用 US$
                    {create.data?.job_id === jobId
                      ? create.data.estimated_provider_cost_usd
                      : estimate.data?.estimated_provider_cost_usd ?? "—"}
                  </div>
                </div>
                <div className="mt-5 grid grid-cols-3 gap-3">
                  <Stat label="结果" value={metrics.total} />
                  <Stat label="可导入" value={metrics.new} />
                  <Stat label="已在库" value={metrics.imported} />
                </div>
              </section>

              {search.data.status === "succeeded" && results.length ? (
                <section className="overflow-hidden rounded-xl border border-border bg-surface shadow-panel">
                  <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border p-4">
                    <label className="inline-flex items-center gap-2 text-xs font-medium">
                      <input
                        checked={allFreshSelected}
                        className="accent-blue-600"
                        onChange={() =>
                          setSelected(
                            allFreshSelected
                              ? []
                              : freshResults.map((item) => item.id),
                          )
                        }
                        type="checkbox"
                      />
                      选择本页未导入内容
                    </label>
                    {selected.length ? (
                      <button
                        className="inline-flex items-center gap-2 rounded-lg bg-primary-600 px-3.5 py-2 text-xs font-medium text-white disabled:opacity-50"
                        disabled={importer.isPending || !permission.canEdit}
                        onClick={() => importer.mutate(selected)}
                        type="button"
                      >
                        {importer.isPending ? (
                          <LoaderCircle aria-hidden="true" className="animate-spin" size={14} />
                        ) : (
                          <Sparkles aria-hidden="true" size={14} />
                        )}
                        导入并增强 {selected.length} 条
                      </button>
                    ) : null}
                  </div>
                  {importer.isSuccess ? (
                    <div className="flex items-center justify-between gap-3 border-b border-emerald-100 bg-emerald-50 px-4 py-3 text-xs text-emerald-800">
                      <span>
                        已创建 {importer.data.inspiration_ids.length} 条灵感；
                        {importer.data.hydration_job_ids.length} 个详情任务仍在后台处理。
                      </span>
                      <Link className="font-semibold underline" href={`/w/${workspaceId}/jobs`}>
                        查看任务
                      </Link>
                    </div>
                  ) : null}
                  <div className="divide-y divide-border">
                    {results.map((result) => (
                      <ResultRow
                        checked={selected.includes(result.id)}
                        disabled={Boolean(result.imported_external_content_id)}
                        key={result.id}
                        onToggle={() =>
                          setSelected((current) =>
                            current.includes(result.id)
                              ? current.filter((id) => id !== result.id)
                              : [...current, result.id],
                          )
                        }
                        result={result}
                      />
                    ))}
                  </div>
                </section>
              ) : search.data.status === "failed" ? (
                <section className="rounded-xl border border-red-100 bg-red-50 p-6">
                  <h2 className="font-semibold text-red-800">搜索任务失败</h2>
                  <p className="mt-2 text-sm text-red-700">
                    {search.data.error_code ?? "供应商暂时不可用"}。已入库历史内容仍可正常浏览。
                  </p>
                </section>
              ) : (
                <section className="rounded-xl border border-border bg-surface p-8 text-center">
                  <LoaderCircle
                    aria-hidden="true"
                    className="mx-auto animate-spin text-primary-600"
                    size={26}
                  />
                  <h2 className="mt-4 font-semibold">搜索任务处理中</h2>
                  <p className="mt-2 text-sm text-text-muted">
                    页面会自动刷新状态；“已创建”不等于“搜索完成”。
                  </p>
                </section>
              )}
            </>
          ) : null}
        </main>
      </div>
    </>
  );
}

function ResultRow({
  result,
  checked,
  disabled,
  onToggle,
}: {
  result: DiscoveryResult;
  checked: boolean;
  disabled: boolean;
  onToggle: () => void;
}) {
  const summary = result.summary;
  const title = textValue(summary.title) || textValue(summary.body_text) || `搜索结果 #${result.result_rank}`;
  const author = objectValue(summary.author_snapshot);
  const metrics = objectValue(summary.metrics);
  const url = textValue(summary.canonical_url);

  return (
    <article className="grid gap-3 p-4 sm:grid-cols-[28px_1fr_auto] sm:items-center">
      <input
        aria-label={`选择 ${title}`}
        checked={checked}
        className="accent-blue-600"
        disabled={disabled}
        onChange={onToggle}
        type="checkbox"
      />
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-[11px] font-semibold text-primary-600">
            #{result.result_rank}
          </span>
          <h3 className="truncate text-sm font-semibold">{title}</h3>
          {disabled ? (
            <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] text-emerald-700">
              <CheckCircle2 aria-hidden="true" size={11} />
              已在灵感库
            </span>
          ) : null}
        </div>
        <p className="mt-1 truncate text-xs text-text-muted">
          {textValue(author.display_name) || "公开内容"} · 赞{" "}
          {metricValue(metrics.likes)} · 评论 {metricValue(metrics.comments)} · 收藏{" "}
          {metricValue(metrics.favorites)}
        </p>
      </div>
      {url ? (
        <a
          aria-label="打开原内容"
          className="grid size-8 place-items-center rounded-lg text-text-muted hover:bg-surface-subtle hover:text-text"
          href={url}
          rel="noreferrer"
          target="_blank"
        >
          <ExternalLink aria-hidden="true" size={15} />
        </a>
      ) : null}
    </article>
  );
}

function textValue(value: unknown) {
  return typeof value === "string" ? value : "";
}

function objectValue(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function metricValue(value: unknown) {
  return typeof value === "number" ? formatCompactNumber(value) : "—";
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg bg-canvas/70 p-3">
      <p className="text-[10px] text-text-muted">{label}</p>
      <strong className="mt-1 block text-xl font-semibold tabular-nums">{value}</strong>
    </div>
  );
}

function searchStatusLabel(status: string) {
  return (
    {
      pending: "等待中",
      running: "搜索中",
      succeeded: "已完成",
      failed: "失败",
    }[status] ?? status
  );
}

function sortLabel(value: unknown) {
  if (value === "popularity_descending") return "热度";
  if (value === "time_descending") return "时间";
  if (value === "comment_descending") return "评论";
  if (value === "collect_descending") return "收藏";
  return "综合";
}
