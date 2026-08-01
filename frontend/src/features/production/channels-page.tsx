"use client";

import {
  ArrowRight,
  BarChart3,
  CheckCircle2,
  Eye,
  MessageCircleMore,
  Plus,
  Search,
  Send,
  UsersRound,
} from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";
import { EmptyState } from "@/src/components/ui/empty-state";
import { ErrorState } from "@/src/components/ui/error-state";
import { PageHeader } from "@/src/components/ui/page-header";
import {
  formatRate,
  PlatformMark,
  summarizePerformance,
} from "@/src/features/production/channel-analytics";
import { useWorkspaceRole } from "@/src/features/identity/queries";
import {
  useChannels,
  useCreateChannel,
  usePerformance,
} from "@/src/features/production/queries";
import type { OwnedChannelCreate } from "@/src/features/production/types";
import {
  Dialog,
  InlineError,
  inputClass,
  primaryButton,
  textareaClass,
} from "@/src/features/production/ui";
import {
  formatCompactNumber,
  formatRelativeTime,
  platformLabel,
} from "@/src/lib/format";

const platformFilters = [
  { label: "全部", value: "all" },
  { label: "Twitter", value: "x" },
  { label: "小红书", value: "xiaohongshu" },
  { label: "抖音", value: "douyin" },
] as const;

export function ChannelsPage({ workspaceId }: { workspaceId: string }) {
  const channels = useChannels(workspaceId);
  const performance = usePerformance(workspaceId, 30);
  const permission = useWorkspaceRole(workspaceId);
  const [open, setOpen] = useState(false);
  const [platform, setPlatform] = useState("all");
  const [query, setQuery] = useState("");

  const visibleChannels = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    return (channels.data ?? []).filter((channel) => {
      const matchesPlatform = platform === "all" || channel.platform === platform;
      const matchesQuery =
        !normalized ||
        [channel.display_name, channel.handle, platformLabel(channel.platform)]
          .filter(Boolean)
          .some((value) => String(value).toLowerCase().includes(normalized));
      return matchesPlatform && matchesQuery;
    });
  }, [channels.data, platform, query]);

  return (
    <>
      <PageHeader
        eyebrow="账号与定位"
        title="自有账号"
        description="在一个视图中管理 Twitter、小红书和抖音账号，追踪内容表现、增长线索与账号策略。"
        actions={
          permission.canEdit ? (
            <button className={primaryButton} onClick={() => setOpen(true)} type="button">
              <Plus size={16} /> 添加账号
            </button>
          ) : null
        }
      />

      <PortfolioSummary
        accountCount={channels.data?.length ?? 0}
        loading={channels.isLoading || performance.isLoading}
        records={performance.data?.records ?? []}
      />

      <section className="mt-5 overflow-hidden rounded-xl border border-border bg-surface shadow-panel">
        <div className="flex flex-col gap-3 border-b border-border px-4 py-3 lg:flex-row lg:items-center lg:justify-between">
          <div aria-label="平台筛选" className="flex items-center gap-1 overflow-x-auto" role="tablist">
            {platformFilters.map((item) => (
              <button
                aria-selected={platform === item.value}
                className={`shrink-0 rounded-lg px-3 py-2 text-xs font-medium transition ${
                  platform === item.value
                    ? "bg-primary-50 text-primary-700"
                    : "text-text-muted hover:bg-surface-subtle hover:text-text"
                }`}
                key={item.value}
                onClick={() => setPlatform(item.value)}
                role="tab"
                type="button"
              >
                {item.label}
              </button>
            ))}
          </div>
          <label className="relative block w-full lg:w-72">
            <Search aria-hidden="true" className="absolute top-1/2 left-3 -translate-y-1/2 text-text-muted" size={15} />
            <span className="sr-only">搜索账号</span>
            <input
              className={`${inputClass} min-h-10 pl-9`}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="搜索账号名称或 @handle"
              value={query}
            />
          </label>
        </div>

        {channels.isLoading ? (
          <div aria-label="正在加载账号" className="divide-y divide-border">
            {Array.from({ length: 3 }).map((_, index) => (
              <div className="h-24 animate-pulse bg-surface-subtle/70" key={index} />
            ))}
          </div>
        ) : channels.error ? (
          <ErrorState message="自有账号暂时不可用。" onRetry={() => channels.refetch()} />
        ) : visibleChannels.length ? (
          <div>
            <div className="hidden grid-cols-[minmax(260px,1.6fr)_minmax(140px,.8fr)_repeat(4,minmax(90px,.55fr))_32px] items-center gap-4 border-b border-border bg-surface-subtle/70 px-5 py-3 text-[11px] font-medium text-text-muted xl:grid">
              <span>账号</span><span>数据状态</span><span>30 天内容</span><span>曝光</span><span>互动率</span><span>转化</span><span />
            </div>
            {visibleChannels.map((channel) => {
              const records = (performance.data?.records ?? []).filter(
                (record) => record.owned_channel_id === channel.id,
              );
              const summary = summarizePerformance(records);
              const latest = [...records].sort(
                (a, b) => new Date(b.published_at).getTime() - new Date(a.published_at).getTime(),
              )[0];
              return (
                <Link
                  className="group grid gap-4 border-b border-border px-5 py-5 transition last:border-0 hover:bg-surface-subtle/60 xl:grid-cols-[minmax(260px,1.6fr)_minmax(140px,.8fr)_repeat(4,minmax(90px,.55fr))_32px] xl:items-center"
                  href={`/w/${workspaceId}/channels/${channel.id}`}
                  key={channel.id}
                >
                  <div className="flex min-w-0 items-center gap-3">
                    <PlatformMark platform={channel.platform} />
                    <div className="min-w-0">
                      <h2 className="truncate text-sm font-semibold">{channel.display_name}</h2>
                      <p className="mt-1 truncate text-xs text-text-muted">
                        {channel.handle || "未设置 handle"} · {platformLabel(channel.platform)}
                      </p>
                    </div>
                  </div>
                  <div>
                    <span className="inline-flex items-center gap-1.5 text-xs font-medium">
                      <CheckCircle2 className={channel.active ? "text-success" : "text-text-muted"} size={14} />
                      {channel.active ? "账号运行中" : "已停用"}
                    </span>
                    <p className="mt-1 text-[11px] text-text-muted">
                      {latest ? `最新数据 ${formatRelativeTime(latest.published_at)}` : "等待录入复盘数据"}
                    </p>
                  </div>
                  <AccountMetric icon={Send} label="30 天内容" value={summary.published.toString()} />
                  <AccountMetric icon={Eye} label="曝光" value={formatCompactNumber(summary.exposure)} />
                  <AccountMetric icon={MessageCircleMore} label="互动率" value={formatRate(summary.engagementRate)} />
                  <AccountMetric icon={BarChart3} label="转化" value={summary.conversions.toLocaleString()} />
                  <ArrowRight className="hidden text-text-muted transition group-hover:translate-x-0.5 group-hover:text-primary-700 xl:block" size={17} />
                </Link>
              );
            })}
          </div>
        ) : (
          <EmptyState
            action={
              permission.canEdit && !channels.data?.length ? (
                <button className={primaryButton} onClick={() => setOpen(true)} type="button">
                  添加第一个账号
                </button>
              ) : undefined
            }
            description={channels.data?.length ? "试试更换平台或搜索关键词。" : "添加账号后，可统一查看发布表现、内容排名和账号定位。"}
            title={channels.data?.length ? "没有符合条件的账号" : "还没有自有账号"}
          />
        )}
      </section>

      <p className="mt-3 text-[11px] leading-5 text-text-muted">
        当前分析来自已登记的发布记录与 24h / 7d / 30d 复盘；尚未接入平台回传的账号会如实显示为等待数据。
      </p>

      <CreateChannelDialog
        onClose={() => setOpen(false)}
        open={open && permission.canEdit}
        workspaceId={workspaceId}
      />
    </>
  );
}

function PortfolioSummary({
  accountCount,
  records,
  loading,
}: {
  accountCount: number;
  records: NonNullable<ReturnType<typeof usePerformance>["data"]>["records"];
  loading: boolean;
}) {
  const summary = summarizePerformance(records);
  const items = [
    { icon: UsersRound, label: "账号数量", value: accountCount.toString(), helper: "Twitter · 小红书 · 抖音" },
    { icon: Send, label: "近 30 天发布", value: summary.published.toString(), helper: `${records.filter((item) => item.latest_review_window).length} 条已复盘` },
    { icon: Eye, label: "总曝光", value: formatCompactNumber(summary.exposure), helper: "来自选定复盘窗口" },
    { icon: MessageCircleMore, label: "总互动", value: formatCompactNumber(summary.interactions), helper: `整体互动率 ${formatRate(summary.engagementRate)}` },
  ];
  return (
    <section aria-label="账号组合概览" className="grid grid-cols-2 overflow-hidden rounded-xl border border-border bg-surface shadow-panel xl:grid-cols-4">
      {items.map((item) => (
        <div className="border-r border-b border-border p-4 even:border-r-0 nth-[n+3]:border-b-0 xl:border-r xl:border-b-0 xl:p-5 xl:last:border-r-0" key={item.label}>
          <div className="flex items-center gap-2 text-xs text-text-muted"><item.icon size={15} />{item.label}</div>
          {loading ? <div className="mt-3 h-8 w-24 animate-pulse rounded bg-surface-subtle" /> : <strong className="mt-3 block text-2xl font-semibold tracking-tight tabular-nums">{item.value}</strong>}
          <p className="mt-1 text-[11px] text-text-muted">{item.helper}</p>
        </div>
      ))}
    </section>
  );
}

function AccountMetric({ icon: Icon, label, value }: { icon: typeof Eye; label: string; value: string }) {
  return (
    <div className="flex items-center justify-between xl:block">
      <span className="flex items-center gap-1.5 text-[11px] text-text-muted xl:hidden"><Icon size={13} />{label}</span>
      <strong className="text-sm font-semibold tabular-nums">{value}</strong>
    </div>
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
    external_id: null,
    handle: null,
    positioning: "",
    publishing_mode: "manual",
    content_pillars: [],
    tone_rules: [],
    prohibited_topics: [],
    audience: {},
  });
  return (
    <Dialog
      description="建立账号档案后，即可统一归集发布复盘数据并维护内容定位。"
      onClose={onClose}
      open={open}
      title="添加自有账号"
    >
      <form
        className="grid gap-4"
        onSubmit={(event) => {
          event.preventDefault();
          create.mutate(value, { onSuccess: onClose });
        }}
      >
        <fieldset>
          <legend className="text-sm font-medium">平台</legend>
          <div className="mt-2 grid grid-cols-3 gap-2">
            {[{ value: "x", label: "Twitter" }, { value: "xiaohongshu", label: "小红书" }, { value: "douyin", label: "抖音" }].map((item) => (
              <button
                className={`flex items-center justify-center gap-2 rounded-lg border px-3 py-3 text-xs font-medium transition ${value.platform === item.value ? "border-primary-500 bg-primary-50 text-primary-700" : "border-border hover:bg-surface-subtle"}`}
                key={item.value}
                onClick={() => setValue({ ...value, platform: item.value as OwnedChannelCreate["platform"] })}
                type="button"
              >
                <PlatformMark platform={item.value} size="sm" />{item.label}
              </button>
            ))}
          </div>
        </fieldset>
        <label className="text-sm font-medium">
          账号名称
          <input className={`${inputClass} mt-2`} onChange={(event) => setValue({ ...value, display_name: event.target.value })} placeholder="团队内易识别的名称" required value={value.display_name} />
        </label>
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="text-sm font-medium">
            Handle
            <input className={`${inputClass} mt-2`} onChange={(event) => setValue({ ...value, handle: event.target.value || null })} placeholder="@account" value={value.handle ?? ""} />
          </label>
          <label className="text-sm font-medium">
            平台账号 ID
            <input className={`${inputClass} mt-2`} onChange={(event) => setValue({ ...value, external_id: event.target.value || null })} placeholder="用于匹配同步数据" value={value.external_id ?? ""} />
          </label>
        </div>
        <label className="text-sm font-medium">
          定位摘要
          <textarea className={`${textareaClass} mt-2`} onChange={(event) => setValue({ ...value, positioning: event.target.value })} placeholder="帮助谁，用什么内容解决什么问题" value={value.positioning} />
        </label>
        <InlineError error={create.error} />
        <button className={primaryButton} disabled={create.isPending} type="submit">
          <Plus size={15} /> {create.isPending ? "正在创建…" : "创建账号"}
        </button>
      </form>
    </Dialog>
  );
}
