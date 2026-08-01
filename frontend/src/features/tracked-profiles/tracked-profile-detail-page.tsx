"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import {
  ArrowLeft,
  Check,
  ChevronDown,
  Clock3,
  ExternalLink,
  LoaderCircle,
  Pause,
  Pencil,
  Play,
  RefreshCw,
  Trash2,
  UsersRound,
  X,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { z } from "zod";
import { ErrorState } from "@/src/components/ui/error-state";
import { StatusBadge } from "@/src/components/ui/status-badge";
import { useWorkspaceRole } from "@/src/features/identity/queries";
import { DeleteProfileDialog } from "@/src/features/tracked-profiles/delete-profile-dialog";
import {
  isVideo,
  ProfileOverviewContentCard,
} from "@/src/features/tracked-profiles/profile-overview-content-card";
import {
  useDeleteTrackedProfile,
  useSyncTrackedProfile,
  useToggleTrackedProfile,
  useTrackedProfile,
  useTrackedProfileOverview,
  useUpdateTrackedProfile,
} from "@/src/features/tracked-profiles/queries";
import { ProfileAvatar } from "@/src/features/tracked-profiles/profile-avatar";
import type {
  TrackedProfileOverview,
  TrackedProfileOverviewContent,
} from "@/src/features/tracked-profiles/types";
import {
  formatCompactNumber,
  formatRelativeTime,
  platformLabel,
} from "@/src/lib/format";

const editSchema = z.object({
  display_name: z.string().min(1, "请输入账号名称").max(255),
  priority: z.number().min(0).max(100),
});

type EditValues = z.infer<typeof editSchema>;

export function TrackedProfileDetailPage({
  workspaceId,
  profileId,
}: {
  workspaceId: string;
  profileId: string;
}) {
  const router = useRouter();
  const profile = useTrackedProfile(workspaceId, profileId);
  const overview = useTrackedProfileOverview(workspaceId, profileId);
  const permission = useWorkspaceRole(workspaceId);
  const update = useUpdateTrackedProfile(workspaceId, profileId);
  const toggle = useToggleTrackedProfile(workspaceId);
  const sync = useSyncTrackedProfile(workspaceId);
  const remove = useDeleteTrackedProfile(workspaceId);
  const [editing, setEditing] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [syncAccepted, setSyncAccepted] = useState(false);
  const form = useForm<EditValues>({
    resolver: zodResolver(editSchema),
    defaultValues: { display_name: "", priority: 50 },
  });
  const priority = useWatch({ control: form.control, name: "priority" });

  useEffect(() => {
    if (profile.data) {
      form.reset({
        display_name: profile.data.display_name,
        priority: profile.data.priority,
      });
    }
  }, [form, profile.data]);

  if (profile.isLoading) {
    return (
      <div aria-label="正在加载账号详情" className="animate-pulse space-y-4">
        <div className="h-5 w-28 rounded bg-surface-subtle" />
        <div className="h-32 rounded-xl bg-surface" />
        <div className="grid gap-4 lg:grid-cols-3">
          <div className="h-72 rounded-xl bg-surface lg:col-span-2" />
          <div className="h-72 rounded-xl bg-surface" />
        </div>
      </div>
    );
  }

  if (profile.error || !profile.data) {
    return (
      <div className="rounded-xl border border-border bg-surface">
        <ErrorState
          message={
            (profile.error as { message?: string })?.message ??
            "没有找到这个对标账号。"
          }
          onRetry={() => profile.refetch()}
          requestId={(profile.error as { requestId?: string })?.requestId}
        />
      </div>
    );
  }

  const item = overview.data?.profile ?? profile.data;
  const busy =
    toggle.isPending || sync.isPending || update.isPending || remove.isPending;

  return (
    <>
      <Link
        className="mb-5 inline-flex items-center gap-2 text-xs font-medium text-text-muted hover:text-text"
        href={`/w/${workspaceId}/tracked-profiles`}
      >
        <ArrowLeft aria-hidden="true" size={14} />
        返回对标账号
      </Link>

      <section className="mb-6 rounded-xl border border-border bg-surface p-4 shadow-panel sm:p-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex min-w-0 items-center gap-3.5">
            <ProfileAvatar profile={item} size="lg" />
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <h1 className="truncate text-xl font-semibold tracking-tight sm:text-2xl">
                  {item.display_name}
                </h1>
                <StatusBadge
                  label={syncStatusLabel(item.sync_status)}
                  status={item.sync_status}
                />
              </div>
              <p className="mt-1 text-sm text-text-muted">
                {platformLabel(item.platform)}
                {item.handle ? ` · ${item.handle}` : ""}
              </p>
              <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-text-muted">
                <span className="inline-flex items-center gap-1.5">
                  <UsersRound aria-hidden="true" size={13} />
                  {formatCompactNumber(item.follower_count_latest)} 粉丝
                </span>
                <span className="inline-flex items-center gap-1.5">
                  <Clock3 aria-hidden="true" size={13} />
                  上次采集 {formatRelativeTime(item.last_synced_at)}
                </span>
                <span>
                  {overview.data ? overview.data.recent_content_count : "—"} 条近期内容
                </span>
              </div>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <a
              className="inline-flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-xs font-medium text-text-muted hover:bg-surface-subtle hover:text-text"
              href={item.profile_url}
              rel="noreferrer"
              target="_blank"
            >
              <ExternalLink aria-hidden="true" size={15} />
              平台主页
            </a>
            {permission.canEdit ? (
              <>
                {syncAccepted ? (
                  <Link
                    aria-live="polite"
                    className="text-xs font-medium text-primary-700 hover:underline"
                    href={`/w/${workspaceId}/jobs`}
                  >
                    同步任务已加入队列
                  </Link>
                ) : null}
                <button
                  className="inline-flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-xs font-medium hover:border-primary-300 hover:bg-primary-50 hover:text-primary-700 disabled:opacity-50"
                  disabled={busy || !item.active}
                  onClick={() => {
                    setSyncAccepted(false);
                    sync.mutate(item, {
                      onSuccess: () => setSyncAccepted(true),
                    });
                  }}
                  type="button"
                >
                  {sync.isPending ? (
                    <LoaderCircle
                      aria-hidden="true"
                      className="animate-spin"
                      size={14}
                    />
                  ) : (
                    <RefreshCw aria-hidden="true" size={14} />
                  )}
                  立即同步
                </button>
              </>
            ) : (
              <span className="rounded-full bg-surface-subtle px-3 py-2 text-xs text-text-muted">
                Viewer · 只读
              </span>
            )}
          </div>
        </div>
      </section>

      <ProfileContentsSection
        contents={overview.data?.contents ?? []}
        error={overview.error}
        isLoading={overview.isLoading}
        total={overview.data?.recent_content_count}
        workspaceId={workspaceId}
      />

      {overview.data ? <ProfileContentOverview overview={overview.data} /> : null}

      <details className="group mt-6 overflow-hidden rounded-xl border border-border bg-surface shadow-panel">
        <summary className="flex cursor-pointer list-none items-center justify-between gap-4 px-4 py-4 text-sm font-medium hover:bg-canvas/50 sm:px-5 [&::-webkit-details-marker]:hidden">
          <span>
            监控设置与诊断
            <span className="ml-2 text-xs font-normal text-text-muted">
              优先级 {item.priority} · 下次扫描{item.active ? formatFuture(item.next_scan_at) : "已暂停"}
            </span>
          </span>
          <ChevronDown
            aria-hidden="true"
            className="shrink-0 text-text-muted transition group-open:rotate-180"
            size={17}
          />
        </summary>
        <div className="border-t border-border px-4 py-5 sm:px-5">
          <dl className="grid gap-x-8 gap-y-5 text-sm sm:grid-cols-2 lg:grid-cols-3">
            <Detail label="平台" value={platformLabel(item.platform)} />
            <Detail label="平台账号 ID" value={item.external_id} mono />
            <Detail label="账号 Handle" value={item.handle ?? "—"} />
            <Detail label="扫描策略 ID" value={item.scan_policy_id} mono />
            <Detail label="扫描优先级" value={`${item.priority} / 100`} />
            <Detail
              label="下次扫描"
              value={item.active ? formatFuture(item.next_scan_at) : "已暂停"}
            />
            <Detail
              label="加入时间"
              value={new Date(item.created_at).toLocaleString("zh-CN")}
            />
            <Detail label="最后更新" value={formatRelativeTime(item.updated_at)} />
          </dl>
          {permission.canEdit ? (
            <div className="mt-6 flex flex-wrap gap-2 border-t border-border pt-4">
              <button
                className="inline-flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-xs font-medium hover:bg-surface-subtle disabled:opacity-50"
                disabled={busy}
                onClick={() => setEditing(true)}
                type="button"
              >
                <Pencil aria-hidden="true" size={14} />
                编辑账号
              </button>
              <button
                className="inline-flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-xs font-medium hover:bg-surface-subtle disabled:opacity-50"
                disabled={busy}
                onClick={() => toggle.mutate(item)}
                type="button"
              >
                {item.active ? (
                  <Pause aria-hidden="true" size={14} />
                ) : (
                  <Play aria-hidden="true" size={14} />
                )}
                {item.active ? "暂停监控" : "恢复监控"}
              </button>
              <button
                className="inline-flex items-center gap-2 rounded-lg border border-red-200 px-3 py-2 text-xs font-medium text-danger hover:bg-red-50 disabled:opacity-50"
                disabled={busy}
                onClick={() => setDeleteOpen(true)}
                type="button"
              >
                <Trash2 aria-hidden="true" size={14} />
                删除账号
              </button>
            </div>
          ) : null}
        </div>
      </details>

      {editing ? (
        <div
          aria-labelledby="edit-profile-title"
          aria-modal="true"
          className="fixed inset-0 z-[70] grid place-items-center bg-text/30 p-4 backdrop-blur-sm"
          role="dialog"
        >
          <button
            aria-label="关闭编辑"
            className="absolute inset-0"
            onClick={() => setEditing(false)}
            type="button"
          />
          <form
            className="relative w-full max-w-md rounded-2xl border border-border bg-surface p-6 shadow-popover"
            onSubmit={form.handleSubmit((values) =>
              update.mutate(values, {
                onSuccess: () => setEditing(false),
              }),
            )}
          >
            <div className="flex items-start justify-between">
              <div>
                <p className="text-xs font-semibold tracking-[0.14em] text-primary-600 uppercase">
                  Edit profile
                </p>
                <h2 className="mt-1 text-xl font-semibold" id="edit-profile-title">
                  编辑账号
                </h2>
              </div>
              <button
                aria-label="关闭"
                className="grid size-8 place-items-center rounded-lg text-text-muted hover:bg-surface-subtle"
                onClick={() => setEditing(false)}
                type="button"
              >
                <X aria-hidden="true" size={17} />
              </button>
            </div>

            <label className="mt-6 block">
              <span className="mb-2 block text-sm font-medium">账号名称</span>
              <input
                className="h-11 w-full rounded-lg border border-border px-3 text-sm outline-none focus:border-primary-500"
                {...form.register("display_name")}
              />
              {form.formState.errors.display_name ? (
                <span className="mt-1.5 block text-xs text-danger">
                  {form.formState.errors.display_name.message}
                </span>
              ) : null}
            </label>

            <label className="mt-5 block">
              <span className="mb-2 flex items-center justify-between text-sm font-medium">
                扫描优先级
                <span className="tabular-nums text-primary-600">
                  {priority}
                </span>
              </span>
              <input
                className="w-full accent-blue-600"
                max={100}
                min={0}
                type="range"
                {...form.register("priority", { valueAsNumber: true })}
              />
            </label>

            {update.error ? (
              <div className="mt-4 rounded-lg border border-red-100 bg-red-50 px-3 py-2.5 text-xs text-red-700">
                {(update.error as { message?: string }).message ??
                  "保存失败，请重试。"}
              </div>
            ) : null}

            <div className="mt-6 flex justify-end gap-2">
              <button
                className="rounded-lg border border-border px-4 py-2.5 text-sm font-medium hover:bg-surface-subtle"
                onClick={() => setEditing(false)}
                type="button"
              >
                取消
              </button>
              <button
                className="inline-flex items-center gap-2 rounded-lg bg-primary-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-primary-700 disabled:opacity-60"
                disabled={update.isPending}
                type="submit"
              >
                {update.isPending ? (
                  <LoaderCircle
                    aria-hidden="true"
                    className="animate-spin"
                    size={15}
                  />
                ) : (
                  <Check aria-hidden="true" size={15} />
                )}
                保存修改
              </button>
            </div>
          </form>
        </div>
      ) : null}
      <DeleteProfileDialog
        error={remove.error}
        onClose={() => {
          if (!remove.isPending) setDeleteOpen(false);
        }}
        onConfirm={() => {
          remove.mutate(item, {
            onSuccess: () => {
              setDeleteOpen(false);
              router.push(`/w/${workspaceId}/tracked-profiles`);
            },
          });
        }}
        open={deleteOpen}
        pending={remove.isPending}
        profile={item}
      />
    </>
  );
}

export type ProfileContentsSectionProps = {
  contents: TrackedProfileOverviewContent[];
  workspaceId: string;
  isLoading?: boolean;
  error?: unknown;
  total?: number;
};

export function ProfileContentsSection({
  contents,
  workspaceId,
  isLoading = false,
  error,
  total,
}: ProfileContentsSectionProps) {
  const [filter, setFilter] = useState<"all" | "high" | "image" | "video">(
    "all",
  );
  const [sort, setSort] = useState<"published" | "collected">("published");
  const contentCount = total ?? contents.length;
  const visibleContents = [...contents]
    .filter((content) => {
      if (filter === "all") return true;
      if (filter === "high") {
        return ["t1", "t2", "qualified"].includes(
          content.latest_score?.grade.toLowerCase() ?? "",
        );
      }
      return filter === "video"
        ? isVideo(content.content_type)
        : !isVideo(content.content_type);
    })
    .sort((left, right) => {
      const leftDate =
        sort === "published"
          ? (left.published_at ?? left.first_seen_at)
          : left.first_seen_at;
      const rightDate =
        sort === "published"
          ? (right.published_at ?? right.first_seen_at)
          : right.first_seen_at;
      return new Date(rightDate).getTime() - new Date(leftDate).getTime();
    });

  return (
    <section aria-labelledby="recent-profile-contents" className="min-w-0">
      <div className="mb-4 flex flex-col gap-4">
        <div>
          <h2
            className="text-xl font-semibold tracking-tight sm:text-2xl"
            id="recent-profile-contents"
          >
            最近采集内容
          </h2>
          <p className="mt-1 text-sm leading-6 text-text-muted">
            优先浏览这个账号最近发布的内容，快速判断值得继续拆解的主题和表达。
          </p>
        </div>
        <div className="flex flex-col gap-3 border-b border-border sm:flex-row sm:items-center sm:justify-between">
          <div className="flex min-w-0 items-center gap-1 overflow-x-auto">
            {[
              { label: "全部", value: "all" as const },
              { label: "高潜内容", value: "high" as const },
              { label: "图文", value: "image" as const },
              { label: "视频", value: "video" as const },
            ].map((option) => (
              <button
                aria-pressed={filter === option.value}
                className={`shrink-0 border-b-2 px-3 py-2 text-sm font-medium transition ${
                  filter === option.value
                    ? "border-primary-600 text-primary-700"
                    : "border-transparent text-text-muted hover:text-text"
                }`}
                key={option.value}
                onClick={() => setFilter(option.value)}
                type="button"
              >
                {option.label}
              </button>
            ))}
          </div>
          <div className="mb-2 flex shrink-0 items-center justify-between gap-3 sm:justify-end">
            <span className="text-xs text-text-muted">最近入库 {contentCount} 条</span>
            <select
              aria-label="内容排序"
              className="h-8 rounded-lg border border-border bg-surface px-2.5 text-xs outline-none focus:border-primary-500"
              onChange={(event) =>
                setSort(event.target.value as "published" | "collected")
              }
              value={sort}
            >
              <option value="published">最新发布</option>
              <option value="collected">最新采集</option>
            </select>
          </div>
        </div>
      </div>

      {isLoading ? (
        <div
          aria-label="正在加载最近采集内容"
          className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4"
        >
          {Array.from({ length: 6 }).map((_, index) => (
            <div
              className="overflow-hidden rounded-xl border border-border bg-surface"
              key={index}
            >
              <div className="aspect-[16/9] animate-pulse bg-surface-subtle" />
              <div className="space-y-3 p-4">
                <div className="h-4 w-4/5 animate-pulse rounded bg-surface-subtle" />
                <div className="h-3 w-full animate-pulse rounded bg-surface-subtle" />
                <div className="h-3 w-2/3 animate-pulse rounded bg-surface-subtle" />
              </div>
            </div>
          ))}
        </div>
      ) : error ? (
        <div className="rounded-xl border border-amber-100 bg-amber-50 p-5 text-sm leading-6 text-amber-800">
          最近内容暂时读取失败。你可以稍后重试，账号本身的同步状态不受影响。
        </div>
      ) : visibleContents.length ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {visibleContents.map((content) => (
            <ProfileOverviewContentCard
              item={content}
              key={content.id}
              workspaceId={workspaceId}
            />
          ))}
        </div>
      ) : (
        <div className="rounded-xl border border-dashed border-border bg-surface px-5 py-12 text-center shadow-panel">
          <p className="text-sm font-medium">
            {contents.length ? "当前筛选下没有内容" : "尚未采集到内容"}
          </p>
          <p className="mx-auto mt-2 max-w-md text-xs leading-5 text-text-muted">
            {contents.length
              ? "切换到全部内容，查看这个账号最近入库的作品。"
              : "发起同步后，可在任务中心确认任务完成，再回到这里查看已入库内容。"}
          </p>
        </div>
      )}
    </section>
  );
}

function ProfileContentOverview({
  overview,
}: {
  overview: TrackedProfileOverview;
}) {
  const distribution = [
    {
      key: "t1",
      label: "T1 现象级",
      value: overview.grade_distribution.t1,
      color: "bg-grade-t1",
    },
    {
      key: "t2",
      label: "T2 爆款",
      value: overview.grade_distribution.t2,
      color: "bg-grade-t2",
    },
    {
      key: "t3",
      label: "T3 小爆",
      value: overview.grade_distribution.t3,
      color: "bg-grade-t3",
    },
    {
      key: "qualified",
      label: "已过硬门槛",
      value: overview.grade_distribution.qualified,
      color: "bg-primary-500",
    },
    {
      key: "normal",
      label: "普通 / 未分级",
      value: overview.grade_distribution.normal,
      color: "bg-text-muted/30",
    },
  ];
  const gradedTotal = distribution.reduce((sum, item) => sum + item.value, 0);

  return (
    <section
      aria-label="内容表现概览"
      className="mt-6 grid gap-4 lg:grid-cols-[0.42fr_0.58fr]"
    >
      <div className="rounded-xl border border-border bg-surface p-5 shadow-panel">
        <div className="flex items-baseline justify-between gap-3">
          <h2 className="text-base font-semibold">内容表现概览</h2>
          <span className="text-xs text-text-muted">最近 {overview.window_days} 天</span>
        </div>
        <dl className="mt-5 grid grid-cols-2 gap-4">
          <div>
            <dt className="text-xs text-text-muted">近期内容</dt>
            <dd className="mt-1 text-2xl font-semibold tabular-nums">
              {overview.recent_content_count}
            </dd>
          </div>
          <div>
            <dt className="text-xs text-text-muted">累计采集</dt>
            <dd className="mt-1 text-2xl font-semibold tabular-nums">
              {overview.total_content_count}
            </dd>
          </div>
        </dl>
      </div>

      <div className="rounded-xl border border-border bg-surface p-5 shadow-panel">
        <h2 className="text-base font-semibold">内容分级分布</h2>
        {gradedTotal ? (
          <>
            <div
              aria-label="内容分级比例"
              className="mt-5 flex h-2.5 overflow-hidden rounded-full bg-surface-subtle"
            >
              {distribution.map((grade) => (
                <span
                  className={grade.color}
                  key={grade.key}
                  style={{ width: `${(grade.value / gradedTotal) * 100}%` }}
                />
              ))}
            </div>
            <div className="mt-4 grid gap-2 text-xs text-text-muted sm:grid-cols-2 xl:grid-cols-5">
              {distribution.map((grade) => (
                <div className="flex items-center gap-2" key={grade.key}>
                  <span className={`size-2 shrink-0 rounded-full ${grade.color}`} />
                  <span>
                    {grade.label} {grade.value}
                  </span>
                </div>
              ))}
            </div>
          </>
        ) : (
          <p className="mt-5 text-sm text-text-muted">当前时间窗口内还没有可分级内容。</p>
        )}
      </div>
    </section>
  );
}

function Detail({
  label,
  value,
  mono,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div>
      <dt className="text-xs text-text-muted">{label}</dt>
      <dd
        className={`mt-1.5 break-all font-medium ${mono ? "font-mono text-xs" : ""}`}
      >
        {value}
      </dd>
    </div>
  );
}

function syncStatusLabel(status: string) {
  return (
    {
      idle: "正常",
      paused: "已暂停",
      pending: "等待中",
      running: "同步中",
      syncing: "同步中",
      failed: "同步失败",
      error: "同步失败",
      dead: "需要处理",
    }[status] ?? status
  );
}

function formatFuture(value: string | null) {
  if (!value) return "待计划";
  const minutes = Math.floor(
    (new Date(value).getTime() - Date.now()) / 60_000,
  );
  if (minutes <= 0) return "即将开始";
  if (minutes < 60) return `${minutes} 分钟后`;
  const hours = Math.floor(minutes / 60);
  return hours < 24 ? `${hours} 小时后` : `${Math.floor(hours / 24)} 天后`;
}
