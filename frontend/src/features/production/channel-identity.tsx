"use client";

import { AlertCircle, CheckCircle2, Loader2, RefreshCw } from "lucide-react";
import { useScanChannel } from "@/src/features/production/queries";
import type { OwnedChannel } from "@/src/features/production/types";

const avatarSizeClasses = {
  sm: "size-10 text-xs",
  lg: "size-14 text-base",
} as const;

export function ChannelAvatar({
  channel,
  size = "sm",
}: {
  channel: Pick<OwnedChannel, "avatar_url" | "display_name">;
  size?: keyof typeof avatarSizeClasses;
}) {
  const initials = Array.from(channel.display_name.trim())
    .slice(0, 2)
    .join("")
    .toUpperCase();

  return (
    <span
      aria-hidden="true"
      className={`relative grid shrink-0 place-items-center overflow-hidden rounded-full bg-gradient-to-br from-primary-100 to-blue-50 font-semibold text-primary-700 ${avatarSizeClasses[size]}`}
    >
      {initials}
      {channel.avatar_url ? (
        // Remote provider URLs are intentionally rendered with a native image so
        // each source can supply its own host without Next image configuration.
        // eslint-disable-next-line @next/next/no-img-element
        <img
          alt=""
          className="absolute inset-0 size-full object-cover"
          decoding="async"
          loading="lazy"
          onError={(event) => {
            event.currentTarget.style.display = "none";
          }}
          referrerPolicy="no-referrer"
          src={channel.avatar_url}
        />
      ) : null}
    </span>
  );
}

export function SyncStatusChip({
  channel,
  workspaceId,
  canEdit,
}: {
  channel: OwnedChannel;
  workspaceId: string;
  canEdit: boolean;
}) {
  const scan = useScanChannel(workspaceId);

  if (channel.sync_status === "synced") {
    return (
      <span className="inline-flex items-center gap-1 text-xs font-medium text-success">
        <CheckCircle2 size={13} />
        已确认
      </span>
    );
  }
  if (channel.sync_status === "pending" || channel.sync_status === "syncing") {
    return (
      <span className="inline-flex items-center gap-1 text-xs font-medium text-text-muted">
        <Loader2 className="animate-spin" size={13} />
        正在扫描账号信息
      </span>
    );
  }
  if (channel.sync_status === "paused" || !channel.active) {
    return (
      <span className="inline-flex items-center gap-1 text-xs font-medium text-text-muted">
        <AlertCircle size={13} />
        已停用，未扫描
      </span>
    );
  }
  if (channel.sync_status === "idle") {
    return (
      <span className="inline-flex items-center gap-1 text-xs font-medium text-text-muted">
        <AlertCircle size={13} />
        待扫描
        {canEdit && channel.external_id ? (
          <RetryScanButton channel={channel} scan={scan} />
        ) : null}
      </span>
    );
  }
  return (
    <span
      className="inline-flex items-center gap-1.5 text-xs font-medium text-danger"
      title={channel.sync_error ?? "扫描失败"}
    >
      <AlertCircle size={13} />
      扫描失败
      {canEdit && channel.external_id ? (
        <RetryScanButton channel={channel} scan={scan} />
      ) : null}
    </span>
  );
}

function RetryScanButton({
  channel,
  scan,
}: {
  channel: OwnedChannel;
  scan: ReturnType<typeof useScanChannel>;
}) {
  return (
    <button
      className="inline-flex items-center gap-1 rounded border border-border bg-surface px-1.5 py-0.5 text-[11px] font-medium text-text-muted transition hover:bg-surface-subtle hover:text-text"
      disabled={scan.isPending}
      onClick={(event) => {
        event.preventDefault();
        event.stopPropagation();
        scan.mutate(channel.id);
      }}
      title={channel.sync_error ?? "重新扫描账号信息"}
      type="button"
    >
      <RefreshCw className={scan.isPending ? "animate-spin" : ""} size={11} />
      {scan.isPending ? "扫描中" : "重新扫描"}
    </button>
  );
}
