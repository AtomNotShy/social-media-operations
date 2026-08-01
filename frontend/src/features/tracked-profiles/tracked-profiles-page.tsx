"use client";

import {
  ArrowUpRight,
  Pause,
  Play,
  Plus,
  RefreshCw,
  Search,
  Trash2,
  UsersRound,
} from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { EmptyState } from "@/src/components/ui/empty-state";
import { ErrorState } from "@/src/components/ui/error-state";
import { PageHeader } from "@/src/components/ui/page-header";
import { StatusBadge } from "@/src/components/ui/status-badge";
import { CreateProfileDialog } from "@/src/features/tracked-profiles/create-profile-dialog";
import { DeleteProfileDialog } from "@/src/features/tracked-profiles/delete-profile-dialog";
import { ProfileAvatar } from "@/src/features/tracked-profiles/profile-avatar";
import { useWorkspaceRole } from "@/src/features/identity/queries";
import {
  useDeleteTrackedProfile,
  useSyncTrackedProfile,
  useToggleTrackedProfile,
  useTrackedProfiles,
} from "@/src/features/tracked-profiles/queries";
import { buildTrackedProfilesSearchHref } from "@/src/features/tracked-profiles/navigation";
import type { TrackedProfile } from "@/src/features/tracked-profiles/types";
import {
  formatCompactNumber,
  formatRelativeTime,
  platformLabel,
} from "@/src/lib/format";

export function TrackedProfilesPage({ workspaceId }: { workspaceId: string }) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const search = searchParams.toString();
  const [queryInput, setQueryInput] = useState(searchParams.get("q") ?? "");
  const [createOpen, setCreateOpen] = useState(
    searchParams.get("create") === "1",
  );
  const activeParam = searchParams.get("active");
  const active =
    activeParam === "true" ? true : activeParam === "false" ? false : undefined;
  const filters = { active, q: searchParams.get("q") ?? undefined };
  const profiles = useTrackedProfiles(workspaceId, filters);
  const toggle = useToggleTrackedProfile(workspaceId);
  const sync = useSyncTrackedProfile(workspaceId);
  const remove = useDeleteTrackedProfile(workspaceId);
  const [deleteTarget, setDeleteTarget] = useState<TrackedProfile | null>(null);
  const permission = useWorkspaceRole(workspaceId);

  useEffect(() => {
    const href = buildTrackedProfilesSearchHref({
      workspaceId,
      search,
      query: queryInput,
    });
    if (!href) return;

    const timeout = window.setTimeout(() => {
      router.replace(href, { scroll: false });
    }, 350);
    return () => window.clearTimeout(timeout);
  }, [queryInput, router, search, workspaceId]);

  const stats = useMemo(() => {
    const items = profiles.data ?? [];
    return {
      total: items.length,
      active: items.filter((item) => item.active).length,
      syncing: items.filter((item) =>
        ["pending", "running", "syncing"].includes(item.sync_status),
      ).length,
      needsAttention: items.filter((item) =>
        ["failed", "dead", "error"].includes(item.sync_status),
      ).length,
    };
  }, [profiles.data]);

  function setActiveFilter(value?: boolean) {
    const params = new URLSearchParams(searchParams.toString());
    if (value == null) params.delete("active");
    else params.set("active", String(value));
    params.delete("cursor");
    const suffix = params.toString();
    router.replace(
      `/w/${workspaceId}/tracked-profiles${suffix ? `?${suffix}` : ""}`,
      { scroll: false },
    );
  }

  return (
    <>
      <PageHeader
        eyebrow="内容情报"
        title="对标账号"
        description="从持续跟踪的账号进入最近采集内容，发现值得拆解和转化的选题。"
        actions={permission.canEdit ? (
          <button
            className="inline-flex items-center gap-2 rounded-lg bg-primary-600 px-4 py-2.5 text-sm font-medium text-white shadow-sm hover:bg-primary-700"
            onClick={() => setCreateOpen(true)}
            type="button"
          >
            <Plus aria-hidden="true" size={16} />
            新建对标账号
          </button>
        ) : (
          <span className="rounded-full border border-border bg-surface px-3 py-2 text-xs font-medium text-text-muted">
            只读访问
          </span>
        )}
      />

      <section className="overflow-hidden rounded-xl border border-border bg-surface shadow-panel">
        <div className="flex flex-col gap-3 border-b border-border p-3 sm:flex-row sm:items-center sm:justify-between sm:p-4">
          <div className="relative w-full max-w-md">
            <Search
              aria-hidden="true"
              className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted"
              size={16}
            />
            <input
              aria-label="搜索对标账号"
              className="h-10 w-full rounded-lg border border-border bg-canvas/60 pl-9 pr-3 text-sm outline-none focus:border-primary-500 focus:bg-surface"
              onChange={(event) => setQueryInput(event.target.value)}
              placeholder="搜索账号名称、Handle 或平台"
              value={queryInput}
            />
          </div>
          <div className="flex items-center gap-1 rounded-lg bg-surface-subtle p-1">
            {[
              { label: "全部", value: undefined },
              { label: "监控中", value: true },
              { label: "已暂停", value: false },
            ].map((item) => (
              <button
                className={`rounded-md px-3 py-1.5 text-xs font-medium ${
                  active === item.value
                    ? "bg-surface text-text shadow-sm"
                    : "text-text-muted hover:text-text"
                }`}
                key={item.label}
                onClick={() => setActiveFilter(item.value)}
                type="button"
              >
                {item.label}
              </button>
            ))}
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-x-5 gap-y-2 border-b border-border bg-canvas/35 px-4 py-2.5 text-xs text-text-muted">
          <span>
            <strong className="font-semibold text-text">{stats.total}</strong> 个账号
          </span>
          <span>{stats.active} 个监控中</span>
          {stats.syncing ? <span className="text-primary-700">{stats.syncing} 个正在同步</span> : null}
          {stats.needsAttention ? (
            <span className="font-medium text-danger">{stats.needsAttention} 个需要处理</span>
          ) : (
            <span>暂无同步异常</span>
          )}
        </div>

        {profiles.isLoading ? (
          <div aria-label="正在加载账号" className="divide-y divide-border">
            {Array.from({ length: 4 }).map((_, index) => (
              <div className="flex animate-pulse items-center gap-4 p-5" key={index}>
                <div className="size-10 rounded-full bg-surface-subtle" />
                <div className="flex-1">
                  <div className="h-3 w-32 rounded bg-surface-subtle" />
                  <div className="mt-2 h-2.5 w-20 rounded bg-surface-subtle" />
                </div>
                <div className="h-7 w-20 rounded-full bg-surface-subtle" />
              </div>
            ))}
          </div>
        ) : profiles.error ? (
          <ErrorState
            message={
              (profiles.error as { message?: string }).message ??
              "后端连接暂时不可用。"
            }
            onRetry={() => profiles.refetch()}
            requestId={(profiles.error as { requestId?: string }).requestId}
          />
        ) : profiles.data?.length ? (
          <>
            <div className="hidden overflow-x-auto md:block">
              <table className="w-full min-w-[820px] border-collapse text-left text-sm">
                <thead className="bg-canvas/70 text-xs text-text-muted">
                  <tr>
                    <th className="px-5 py-3 font-medium">账号</th>
                    <th className="px-4 py-3 font-medium">近期内容</th>
                    <th className="px-4 py-3 font-medium">受众规模</th>
                    <th className="px-4 py-3 font-medium">监控状态</th>
                    <th className="px-5 py-3 text-right font-medium">操作</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {profiles.data.map((profile) => (
                    <ProfileRow
                      busy={
                        (toggle.isPending &&
                          toggle.variables?.id === profile.id) ||
                        (sync.isPending && sync.variables?.id === profile.id) ||
                        (remove.isPending && remove.variables?.id === profile.id)
                      }
                      detailHref={`/w/${workspaceId}/tracked-profiles/${profile.id}`}
                      canEdit={permission.canEdit}
                      key={profile.id}
                      onSync={() => sync.mutate(profile)}
                      onToggle={() => toggle.mutate(profile)}
                      onDelete={() => setDeleteTarget(profile)}
                      profile={profile}
                    />
                  ))}
                </tbody>
              </table>
            </div>
            <div className="divide-y divide-border md:hidden">
              {profiles.data.map((profile) => (
                <ProfileCard
                  busy={
                    (toggle.isPending && toggle.variables?.id === profile.id) ||
                    (sync.isPending && sync.variables?.id === profile.id) ||
                    (remove.isPending && remove.variables?.id === profile.id)
                  }
                  detailHref={`/w/${workspaceId}/tracked-profiles/${profile.id}`}
                  canEdit={permission.canEdit}
                  key={profile.id}
                  onSync={() => sync.mutate(profile)}
                  onToggle={() => toggle.mutate(profile)}
                  onDelete={() => setDeleteTarget(profile)}
                  profile={profile}
                />
              ))}
            </div>
          </>
        ) : (
          <EmptyState
            action={permission.canEdit ? (
              <button
                className="inline-flex items-center gap-2 rounded-lg bg-primary-600 px-4 py-2.5 text-sm font-medium text-white"
                onClick={() => setCreateOpen(true)}
                type="button"
              >
                <Plus aria-hidden="true" size={16} />
                添加第一个账号
              </button>
            ) : undefined}
            description="添加一个公开账号后，可按需发起同步并在任务中心追踪进度。"
            title="还没有符合条件的对标账号"
          />
        )}

        <footer className="flex items-center justify-between border-t border-border bg-canvas/40 px-5 py-3 text-xs text-text-muted">
          <span>当前显示 {profiles.data?.length ?? 0} 个账号</span>
          <span className="inline-flex items-center gap-1.5">
            <UsersRound aria-hidden="true" size={14} />
            数据按工作区隔离
          </span>
        </footer>
      </section>

      <CreateProfileDialog
        onClose={() => {
          setCreateOpen(false);
          if (searchParams.has("create")) {
            const params = new URLSearchParams(searchParams.toString());
            params.delete("create");
            const suffix = params.toString();
            router.replace(
              `/w/${workspaceId}/tracked-profiles${suffix ? `?${suffix}` : ""}`,
              { scroll: false },
            );
          }
        }}
        open={createOpen && permission.canEdit}
        workspaceId={workspaceId}
      />
      <DeleteProfileDialog
        error={remove.error}
        onClose={() => {
          if (!remove.isPending) setDeleteTarget(null);
        }}
        onConfirm={() => {
          if (!deleteTarget) return;
          remove.mutate(deleteTarget, {
            onSuccess: () => setDeleteTarget(null),
          });
        }}
        open={deleteTarget !== null}
        pending={remove.isPending}
        profile={deleteTarget}
      />
    </>
  );
}

function ProfileRow({
  profile,
  onSync,
  onToggle,
  onDelete,
  busy,
  detailHref,
  canEdit,
}: {
  profile: TrackedProfile;
  onSync: () => void;
  onToggle: () => void;
  onDelete: () => void;
  busy: boolean;
  detailHref: string;
  canEdit: boolean;
}) {
  return (
    <tr className="group hover:bg-canvas/45">
      <td className="px-5 py-4">
        <ProfileIdentity href={detailHref} profile={profile} />
      </td>
      <td className="px-4 py-4">
        <Link
          className="group/content inline-flex flex-col hover:text-primary-700"
          href={`${detailHref}#recent-profile-contents`}
        >
          <span className="inline-flex items-center gap-1 font-medium">
            查看最近采集内容
            <ArrowUpRight
              aria-hidden="true"
              className="transition group-hover/content:translate-x-0.5 group-hover/content:-translate-y-0.5"
              size={13}
            />
          </span>
          <span className="mt-1 text-xs text-text-muted">
            上次采集 {formatRelativeTime(profile.last_synced_at)}
          </span>
        </Link>
      </td>
      <td className="px-4 py-4">
        <span className="font-medium tabular-nums">
          {formatCompactNumber(profile.follower_count_latest)}
        </span>
        <span className="ml-1 text-xs text-text-muted">粉丝</span>
      </td>
      <td className="px-4 py-4">
        <StatusBadge
          label={syncStatusLabel(profile.sync_status)}
          status={profile.sync_status}
        />
      </td>
      <td className="px-5 py-4">
        {canEdit ? <div className="flex items-center justify-end gap-1">
          <button
            aria-label={`同步 ${profile.display_name}`}
            className="grid size-8 place-items-center rounded-lg text-text-muted hover:bg-primary-50 hover:text-primary-700 disabled:opacity-40"
            disabled={busy || !profile.active}
            onClick={onSync}
            title="立即同步"
            type="button"
          >
            <RefreshCw
              aria-hidden="true"
              className={busy ? "animate-spin" : ""}
              size={15}
            />
          </button>
          <button
            aria-label={`${profile.active ? "暂停" : "恢复"} ${profile.display_name}`}
            className="grid size-8 place-items-center rounded-lg text-text-muted hover:bg-surface-subtle hover:text-text disabled:opacity-40"
            disabled={busy}
            onClick={onToggle}
            title={profile.active ? "暂停" : "恢复"}
            type="button"
          >
            {profile.active ? (
              <Pause aria-hidden="true" size={15} />
            ) : (
              <Play aria-hidden="true" size={15} />
            )}
          </button>
          <button
            aria-label={`删除 ${profile.display_name}`}
            className="grid size-8 place-items-center rounded-lg text-text-muted hover:bg-red-50 hover:text-danger"
            disabled={busy}
            onClick={onDelete}
            type="button"
          >
            <Trash2 aria-hidden="true" size={15} />
          </button>
        </div> : <span className="text-xs text-text-muted">只读</span>}
      </td>
    </tr>
  );
}

function ProfileCard({
  profile,
  onSync,
  onToggle,
  onDelete,
  busy,
  detailHref,
  canEdit,
}: {
  profile: TrackedProfile;
  onSync: () => void;
  onToggle: () => void;
  onDelete: () => void;
  busy: boolean;
  detailHref: string;
  canEdit: boolean;
}) {
  return (
    <article className="p-4">
      <div className="flex items-start justify-between gap-3">
        <ProfileIdentity href={detailHref} profile={profile} />
        <StatusBadge
          label={syncStatusLabel(profile.sync_status)}
          status={profile.sync_status}
        />
      </div>
      <Link
        className="mt-4 flex items-center justify-between gap-3 rounded-lg border border-primary-100 bg-primary-50/60 px-3.5 py-3 text-sm font-medium text-primary-700"
        href={`${detailHref}#recent-profile-contents`}
      >
        查看最近采集内容
        <ArrowUpRight aria-hidden="true" size={15} />
      </Link>
      <dl className="mt-3 grid grid-cols-2 gap-3 text-xs">
        <div>
          <dt className="text-text-muted">粉丝</dt>
          <dd className="mt-1 font-semibold tabular-nums">
            {formatCompactNumber(profile.follower_count_latest)}
          </dd>
        </div>
        <div>
          <dt className="text-text-muted">上次采集</dt>
          <dd className="mt-1 font-semibold">
            {formatRelativeTime(profile.last_synced_at)}
          </dd>
        </div>
      </dl>
      {canEdit ? <div className="mt-3 flex justify-end gap-2">
        <button
          className="inline-flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-xs font-medium disabled:opacity-40"
          disabled={busy || !profile.active}
          onClick={onSync}
          type="button"
        >
          <RefreshCw
            aria-hidden="true"
            className={busy ? "animate-spin" : ""}
            size={14}
          />
          立即同步
        </button>
        <button
          className="inline-flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-xs font-medium disabled:opacity-40"
          disabled={busy}
          onClick={onToggle}
          type="button"
        >
          {profile.active ? (
            <Pause aria-hidden="true" size={14} />
          ) : (
            <Play aria-hidden="true" size={14} />
          )}
          {profile.active ? "暂停" : "恢复"}
        </button>
        <button
          aria-label={`删除 ${profile.display_name}`}
          className="inline-flex items-center gap-2 rounded-lg border border-red-200 px-3 py-2 text-xs font-medium text-danger hover:bg-red-50 disabled:opacity-40"
          disabled={busy}
          onClick={onDelete}
          type="button"
        >
          <Trash2 aria-hidden="true" size={14} />
          删除
        </button>
      </div> : null}
    </article>
  );
}

function ProfileIdentity({
  profile,
  href,
}: {
  profile: TrackedProfile;
  href: string;
}) {
  return (
    <div className="flex min-w-0 items-center gap-3">
      <ProfileAvatar profile={profile} />
      <Link className="min-w-0 hover:text-primary-700" href={href}>
        <span className="flex items-center gap-1 font-medium">
          <span className="truncate">{profile.display_name}</span>
          <ArrowUpRight aria-hidden="true" className="shrink-0 text-text-muted" size={13} />
        </span>
        <span className="mt-0.5 block truncate text-xs text-text-muted">
          {platformLabel(profile.platform)}
          {profile.handle ? ` · ${profile.handle}` : ""}
        </span>
      </Link>
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
