"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import {
  ArrowLeft,
  CalendarClock,
  Check,
  Clock3,
  ExternalLink,
  LoaderCircle,
  Pause,
  Pencil,
  Play,
  RefreshCw,
  ScanSearch,
  ShieldCheck,
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
import { ProfileContentCard } from "@/src/features/inspirations/inspiration-card";
import { useProfileContents } from "@/src/features/inspirations/queries";
import { DeleteProfileDialog } from "@/src/features/tracked-profiles/delete-profile-dialog";
import {
  useDeleteTrackedProfile,
  useSyncTrackedProfile,
  useToggleTrackedProfile,
  useTrackedProfile,
  useUpdateTrackedProfile,
} from "@/src/features/tracked-profiles/queries";
import { ProfileAvatar } from "@/src/features/tracked-profiles/profile-avatar";
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
  const contents = useProfileContents(workspaceId, profileId);
  const permission = useWorkspaceRole(workspaceId);
  const update = useUpdateTrackedProfile(workspaceId, profileId);
  const toggle = useToggleTrackedProfile(workspaceId);
  const sync = useSyncTrackedProfile(workspaceId);
  const remove = useDeleteTrackedProfile(workspaceId);
  const [editing, setEditing] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
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

  const item = profile.data;
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

      <section className="mb-5 overflow-hidden rounded-2xl border border-border bg-surface shadow-panel">
        <div className="h-1.5 bg-gradient-to-r from-primary-600 via-blue-400 to-cyan-300" />
        <div className="flex flex-col gap-5 p-5 sm:p-7 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex min-w-0 items-center gap-4">
            <ProfileAvatar profile={item} size="lg" />
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <h1 className="truncate text-2xl font-semibold tracking-tight">
                  {item.display_name}
                </h1>
                <StatusBadge
                  label={syncStatusLabel(item.sync_status)}
                  status={item.sync_status}
                />
              </div>
              <p className="mt-1.5 text-sm text-text-muted">
                {platformLabel(item.platform)}
                {item.handle ? ` · ${item.handle}` : ""}
              </p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <a
              className="inline-flex items-center gap-2 rounded-lg border border-border px-3.5 py-2.5 text-sm font-medium hover:bg-surface-subtle"
              href={item.profile_url}
              rel="noreferrer"
              target="_blank"
            >
              <ExternalLink aria-hidden="true" size={15} />
              打开主页
            </a>
            {permission.canEdit ? (
              <>
                <button
                  className="inline-flex items-center gap-2 rounded-lg border border-border px-3.5 py-2.5 text-sm font-medium hover:bg-surface-subtle disabled:opacity-50"
                  disabled={busy}
                  onClick={() => setEditing(true)}
                  type="button"
                >
                  <Pencil aria-hidden="true" size={15} />
                  编辑
                </button>
                <button
                  className="inline-flex items-center gap-2 rounded-lg border border-border px-3.5 py-2.5 text-sm font-medium hover:bg-surface-subtle disabled:opacity-50"
                  disabled={busy}
                  onClick={() => toggle.mutate(item)}
                  type="button"
                >
                  {item.active ? (
                    <Pause aria-hidden="true" size={15} />
                  ) : (
                    <Play aria-hidden="true" size={15} />
                  )}
                  {item.active ? "暂停" : "恢复"}
                </button>
                <button
                  className="inline-flex items-center gap-2 rounded-lg bg-primary-600 px-3.5 py-2.5 text-sm font-medium text-white hover:bg-primary-700 disabled:opacity-50"
                  disabled={busy || !item.active}
                  onClick={() => sync.mutate(item)}
                  type="button"
                >
                  {sync.isPending ? (
                    <LoaderCircle
                      aria-hidden="true"
                      className="animate-spin"
                      size={15}
                    />
                  ) : (
                    <RefreshCw aria-hidden="true" size={15} />
                  )}
                  立即同步
                </button>
                <button
                  className="inline-flex items-center gap-2 rounded-lg border border-red-200 px-3.5 py-2.5 text-sm font-medium text-danger hover:bg-red-50 disabled:opacity-50"
                  disabled={busy}
                  onClick={() => setDeleteOpen(true)}
                  type="button"
                >
                  <Trash2 aria-hidden="true" size={15} />
                  删除
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

      <section className="mb-5 grid grid-cols-2 gap-3 xl:grid-cols-4">
        {[
          {
            icon: UsersRound,
            label: "粉丝数",
            value: formatCompactNumber(item.follower_count_latest),
            detail: item.follower_count_latest == null ? "平台暂未提供" : "最新快照",
          },
          {
            icon: ScanSearch,
            label: "扫描优先级",
            value: String(item.priority),
            detail: "范围 0–100",
          },
          {
            icon: Clock3,
            label: "最近同步",
            value: formatRelativeTime(item.last_synced_at),
            detail: item.last_synced_at ? "数据已入库" : "尚未执行",
          },
          {
            icon: CalendarClock,
            label: "下次扫描",
            value: item.active ? formatFuture(item.next_scan_at) : "已暂停",
            detail: item.active ? "按当前策略" : "恢复后重新计划",
          },
        ].map((metric) => (
          <div
            className="rounded-xl border border-border bg-surface p-4 shadow-panel sm:p-5"
            key={metric.label}
          >
            <div className="flex items-center gap-2 text-xs font-medium text-text-muted">
              <metric.icon aria-hidden="true" size={15} />
              {metric.label}
            </div>
            <strong className="mt-3 block text-xl font-semibold tabular-nums">
              {metric.value}
            </strong>
            <p className="mt-1 text-[11px] text-text-muted">{metric.detail}</p>
          </div>
        ))}
      </section>

      <div className="grid gap-5 xl:grid-cols-[1.35fr_0.65fr]">
        <section className="rounded-xl border border-border bg-surface p-5 shadow-panel sm:p-6">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-xs font-semibold tracking-[0.14em] text-primary-600 uppercase">
                Profile
              </p>
              <h2 className="mt-1 text-lg font-semibold">账号资料与扫描配置</h2>
            </div>
            <ShieldCheck aria-hidden="true" className="text-success" size={20} />
          </div>
          <dl className="mt-6 grid gap-x-8 gap-y-5 text-sm sm:grid-cols-2">
            <Detail label="平台" value={platformLabel(item.platform)} />
            <Detail label="平台账号 ID" value={item.external_id} mono />
            <Detail label="账号 Handle" value={item.handle ?? "—"} />
            <Detail label="扫描策略 ID" value={item.scan_policy_id} mono />
            <Detail
              label="加入时间"
              value={new Date(item.created_at).toLocaleString("zh-CN")}
            />
            <Detail
              label="最后更新"
              value={formatRelativeTime(item.updated_at)}
            />
          </dl>
        </section>

        <section className="rounded-xl border border-border bg-surface p-5 shadow-panel sm:p-6">
          <p className="text-xs font-semibold tracking-[0.14em] text-primary-600 uppercase">
            Data availability
          </p>
          <div className="flex items-end justify-between gap-3">
            <h2 className="mt-1 text-lg font-semibold">最近采集作品</h2>
            <span className="text-xs text-text-muted">
              {contents.data?.length ?? 0} 条
            </span>
          </div>
          {contents.isLoading ? (
            <div className="mt-6 space-y-3">
              {Array.from({ length: 2 }).map((_, index) => (
                <div
                  className="h-28 animate-pulse rounded-xl bg-surface-subtle"
                  key={index}
                />
              ))}
            </div>
          ) : contents.error ? (
            <div className="mt-6 rounded-xl border border-amber-100 bg-amber-50 p-4 text-xs leading-5 text-amber-800">
              作品列表暂时读取失败，账号同步状态仍以页面上方为准。
            </div>
          ) : contents.data?.length ? (
            <div className="mt-6 space-y-3">
              {contents.data.slice(0, 6).map((content) => (
                <ProfileContentCard item={content} key={content.id} />
              ))}
            </div>
          ) : (
            <div className="mt-6 rounded-xl border border-dashed border-border bg-canvas/60 p-5 text-center">
              <p className="text-sm font-medium">尚未采集到作品</p>
              <p className="mt-2 text-xs leading-5 text-text-muted">
                发起同步后，可在任务中心确认任务完成，再回到这里查看已入库作品。
              </p>
            </div>
          )}
        </section>
      </div>

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
      failed: "同步失败",
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
