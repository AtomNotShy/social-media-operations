import { ArrowUpRight, Calendar, Gauge, MessageCircle } from "lucide-react";
import Link from "next/link";
import { StatusBadge } from "@/src/components/ui/status-badge";
import {
  authorName,
  contentCoverUrl,
  contentTitle,
  detailStatusLabel,
  engagementTotal,
  formatScoreRatio,
  inspirationStatusLabel,
  inspirationSourceLabel,
  scoreGradeBadge,
} from "@/src/features/inspirations/presentation";
import type {
  ExternalContent,
  Inspiration,
} from "@/src/features/inspirations/types";
import {
  formatCompactNumber,
  formatRelativeTime,
  platformLabel,
} from "@/src/lib/format";

const gradients: Record<string, string> = {
  xiaohongshu: "from-rose-500 via-orange-400 to-amber-300",
  douyin: "from-slate-950 via-fuchsia-800 to-cyan-500",
  bilibili: "from-sky-500 via-blue-400 to-pink-300",
  youtube: "from-red-600 via-red-500 to-orange-400",
};

export function InspirationCard({
  item,
  href,
}: {
  item: Inspiration;
  href: string;
}) {
  const coverUrl = contentCoverUrl(item.content.media_manifest);
  const gradeBadge = scoreGradeBadge(item.latest_score?.grade);
  const scoreRatio = formatScoreRatio(item.latest_score?.r_value);
  const interactions = engagementTotal(item.latest_metrics);

  return (
    <article className="group overflow-hidden rounded-xl border border-border bg-surface shadow-panel transition hover:-translate-y-0.5 hover:shadow-popover">
      <Link href={href}>
        <div
          className={`relative h-36 bg-gradient-to-br p-4 text-white ${gradients[item.content.platform] ?? "from-primary-700 via-primary-500 to-cyan-400"}`}
        >
          {coverUrl ? (
            // Remote provider URLs are intentionally rendered with a native image so
            // each source can supply its own host without Next image configuration.
            // eslint-disable-next-line @next/next/no-img-element
            <img
              alt=""
              className="absolute inset-0 size-full object-cover transition duration-300 group-hover:scale-105"
              decoding="async"
              loading="lazy"
              onError={(event) => {
                event.currentTarget.style.display = "none";
              }}
              referrerPolicy="no-referrer"
              src={coverUrl}
            />
          ) : null}
          <div
            aria-hidden="true"
            className="absolute inset-0 bg-gradient-to-t from-black/75 via-black/15 to-black/10"
          />
          <div className="flex items-start justify-between">
            <span className="rounded-full bg-black/20 px-2.5 py-1 text-[11px] font-medium backdrop-blur-sm">
              {platformLabel(item.content.platform)}
            </span>
            <div className="flex items-center gap-2">
              {gradeBadge ? (
                <span className="rounded-full bg-amber-300 px-2 py-1 text-[11px] font-bold text-amber-950 shadow-sm">
                  {gradeBadge}
                </span>
              ) : null}
              <ArrowUpRight
                aria-hidden="true"
                className="opacity-70 transition group-hover:translate-x-0.5 group-hover:-translate-y-0.5 group-hover:opacity-100"
                size={18}
              />
            </div>
          </div>
          <p className="absolute bottom-4 left-4 right-4 line-clamp-2 text-lg font-semibold leading-6">
            {contentTitle(item.content.title, item.content.body_text)}
          </p>
        </div>
      </Link>
      <div className="p-4">
        <div className="flex items-center justify-between gap-3">
          <p className="truncate text-xs text-text-muted">
            {authorName(item.content.author_snapshot)}
          </p>
          <StatusBadge
            label={inspirationStatusLabel(item.status)}
            status={item.status === "archived" ? "paused" : item.status}
          />
        </div>
        <p className="mt-3 line-clamp-2 min-h-10 text-sm leading-5 text-text-muted">
          {item.content.body_text || "当前内容源未提供正文摘要。"}
        </p>
        {scoreRatio || item.latest_metrics?.views != null || interactions != null ? (
          <div className="mt-3 flex flex-wrap gap-x-3 gap-y-1 text-[11px] font-medium text-text-muted">
            {scoreRatio ? <span title="相对同账号历史基线的 R 倍数">{scoreRatio}</span> : null}
            {item.latest_metrics?.views != null ? (
              <span title="最新采集播放/浏览量">
                热度 {formatCompactNumber(item.latest_metrics.views)}
              </span>
            ) : null}
            {interactions != null ? (
              <span title="点赞、评论、收藏与分享的已知合计">
                互动 {formatCompactNumber(interactions)}
              </span>
            ) : null}
          </div>
        ) : null}
        <div className="mt-4 grid grid-cols-3 gap-2 border-t border-border pt-3 text-[11px] text-text-muted">
          <span className="inline-flex items-center gap-1" title="人工评分">
            <Gauge aria-hidden="true" size={13} />
            人工 {item.manual_score ?? "—"}
          </span>
          <span className="inline-flex items-center gap-1" title="收录来源">
            <MessageCircle aria-hidden="true" size={13} />
            {inspirationSourceLabel(item.source)}
          </span>
          <span className="inline-flex items-center justify-end gap-1">
            <Calendar aria-hidden="true" size={13} />
            {formatRelativeTime(item.content.published_at)}
          </span>
        </div>
        <p className="mt-2 text-[10px] text-text-muted">
          {detailStatusLabel(item.content.detail_status)} · 打开详情页可补全互动指标
        </p>
      </div>
    </article>
  );
}

export function ProfileContentCard({ item }: { item: ExternalContent }) {
  return (
    <a
      className="block rounded-xl border border-border bg-canvas/50 p-4 transition hover:border-primary-300 hover:bg-surface"
      href={item.canonical_url}
      rel="noreferrer"
      target="_blank"
    >
      <div className="flex items-center justify-between gap-3">
        <span className="text-[11px] font-semibold tracking-wide text-primary-600 uppercase">
          {platformLabel(item.platform)} · {item.content_type}
        </span>
        <ArrowUpRight aria-hidden="true" className="text-text-muted" size={15} />
      </div>
      <h3 className="mt-2 line-clamp-2 text-sm font-semibold leading-5">
        {contentTitle(item.title, item.body_text)}
      </h3>
      <p className="mt-2 line-clamp-2 text-xs leading-5 text-text-muted">
        {item.body_text || "当前内容源未提供正文摘要。"}
      </p>
      <p className="mt-3 text-[11px] text-text-muted">
        {detailStatusLabel(item.detail_status)} · {formatRelativeTime(item.published_at)}
      </p>
    </a>
  );
}
