"use client";

import { ArrowRight, CircleUserRound, Plus, RadioTower } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { EmptyState } from "@/src/components/ui/empty-state";
import { ErrorState } from "@/src/components/ui/error-state";
import { PageHeader } from "@/src/components/ui/page-header";
import { StatusBadge } from "@/src/components/ui/status-badge";
import { useWorkspaceRole } from "@/src/features/identity/queries";
import {
  useChannels,
  useCreateChannel,
} from "@/src/features/production/queries";
import type { OwnedChannelCreate } from "@/src/features/production/types";
import {
  Dialog,
  InlineError,
  inputClass,
  primaryButton,
  textareaClass,
} from "@/src/features/production/ui";

const platformLabels: Record<string, string> = {
  xiaohongshu: "小红书",
  douyin: "抖音",
  bilibili: "Bilibili",
  youtube: "YouTube",
  wechat_channels: "视频号",
  tiktok: "TikTok",
  instagram: "Instagram",
};

export function ChannelsPage({ workspaceId }: { workspaceId: string }) {
  const channels = useChannels(workspaceId);
  const permission = useWorkspaceRole(workspaceId);
  const [open, setOpen] = useState(false);

  return (
    <>
      <PageHeader
        eyebrow="账号与定位"
        title="自有账号"
        description="把目标受众、内容支柱、语气规则和事实禁区固化为生产约束。"
        actions={
          permission.canEdit ? (
            <button className={primaryButton} onClick={() => setOpen(true)} type="button">
              <Plus size={16} /> 新建账号
            </button>
          ) : null
        }
      />
      {channels.isLoading ? (
        <div className="grid gap-4 lg:grid-cols-2">
          {Array.from({ length: 4 }).map((_, index) => (
            <div className="h-60 animate-pulse rounded-xl bg-surface" key={index} />
          ))}
        </div>
      ) : channels.error ? (
        <section className="rounded-xl border border-border bg-surface">
          <ErrorState message="自有账号暂时不可用。" onRetry={() => channels.refetch()} />
        </section>
      ) : channels.data?.length ? (
        <div className="grid gap-4 lg:grid-cols-2">
          {channels.data.map((channel) => (
            <Link
              className="group rounded-xl border border-border bg-surface p-5 shadow-panel transition hover:-translate-y-0.5 hover:shadow-popover"
              href={`/w/${workspaceId}/channels/${channel.id}`}
              key={channel.id}
            >
              <div className="flex items-start justify-between gap-4">
                <span className="grid size-11 place-items-center rounded-xl bg-primary-50 text-primary-600">
                  <CircleUserRound size={20} />
                </span>
                <StatusBadge
                  label={channel.active ? "运行中" : "已停用"}
                  status={channel.active ? "succeeded" : "paused"}
                />
              </div>
              <p className="mt-5 text-[10px] font-semibold tracking-[0.14em] text-primary-600 uppercase">
                {platformLabels[channel.platform] ?? channel.platform} ·{" "}
                {channel.publishing_mode === "manual" ? "人工发布" : channel.publishing_mode}
              </p>
              <h2 className="mt-1 flex items-center justify-between text-lg font-semibold">
                {channel.display_name}
                <ArrowRight className="transition group-hover:translate-x-1" size={17} />
              </h2>
              <p className="mt-2 min-h-12 text-sm leading-6 text-text-muted">
                {channel.positioning || "尚未填写账号定位。"}
              </p>
              <div className="mt-4 flex flex-wrap gap-2">
                {channel.content_pillars.slice(0, 3).map((pillar) => (
                  <span
                    className="rounded-full bg-surface-subtle px-2.5 py-1 text-xs"
                    key={String(pillar)}
                  >
                    {String(pillar)}
                  </span>
                ))}
              </div>
              <p className="mt-5 flex items-center gap-2 border-t border-border pt-4 text-xs text-text-muted">
                <RadioTower size={14} />
                {channel.handle || "未设置账号标识"}
              </p>
            </Link>
          ))}
        </div>
      ) : (
        <section className="rounded-xl border border-border bg-surface">
          <EmptyState
            action={
              permission.canEdit ? (
                <button className={primaryButton} onClick={() => setOpen(true)} type="button">
                  新建第一个自有账号
                </button>
              ) : undefined
            }
            description="账号定位是选题、脚本生成与发布排期的基础约束。"
            title="还没有自有账号"
          />
        </section>
      )}
      <CreateChannelDialog
        onClose={() => setOpen(false)}
        open={open && permission.canEdit}
        workspaceId={workspaceId}
      />
    </>
  );
}

function CreateChannelDialog({
  workspaceId,
  open,
  onClose,
}: {
  workspaceId: string;
  open: boolean;
  onClose: () => void;
}) {
  const create = useCreateChannel(workspaceId);
  const [value, setValue] = useState<OwnedChannelCreate>({
    platform: "xiaohongshu",
    display_name: "",
    positioning: "",
    publishing_mode: "manual",
    content_pillars: [],
    tone_rules: [],
    prohibited_topics: [],
    audience: {},
  });
  return (
    <Dialog
      description="先建立最小定位，之后可在账号详情中补充完整规则。"
      onClose={onClose}
      open={open}
      title="新建自有账号"
    >
      <form
        className="grid gap-4"
        onSubmit={(event) => {
          event.preventDefault();
          create.mutate(value, { onSuccess: onClose });
        }}
      >
        <label className="text-sm font-medium">
          平台
          <select
            className={`${inputClass} mt-2`}
            onChange={(event) =>
              setValue({
                ...value,
                platform: event.target.value as OwnedChannelCreate["platform"],
              })
            }
            value={value.platform}
          >
            <option value="xiaohongshu">小红书</option>
            <option value="douyin">抖音</option>
            <option value="bilibili">Bilibili</option>
            <option value="youtube">YouTube</option>
            <option value="wechat_channels">视频号</option>
          </select>
        </label>
        <label className="text-sm font-medium">
          账号名称
          <input
            className={`${inputClass} mt-2`}
            onChange={(event) => setValue({ ...value, display_name: event.target.value })}
            required
            value={value.display_name}
          />
        </label>
        <label className="text-sm font-medium">
          定位摘要
          <textarea
            className={`${textareaClass} mt-2`}
            onChange={(event) => setValue({ ...value, positioning: event.target.value })}
            placeholder="帮助谁，用什么内容解决什么问题"
            value={value.positioning}
          />
        </label>
        <InlineError error={create.error} />
        <button className={primaryButton} disabled={create.isPending} type="submit">
          创建账号
        </button>
      </form>
    </Dialog>
  );
}

