import {
  ArrowUpRight,
  Calendar,
  Eye,
  Image as ImageIcon,
  MessageCircle,
  Play,
} from "lucide-react";
import Link from "next/link";
import type { TrackedProfileOverviewContent } from "@/src/features/tracked-profiles/types";
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

export function ProfileOverviewContentCard({
  item,
  workspaceId,
}: {
  item: TrackedProfileOverviewContent;
  workspaceId: string;
}) {
  const grade = gradeLabel(item.latest_score?.grade);
  const engagement = engagementTotal(item.latest_metrics);
  const inspirationHref =
    item.in_inspiration_library && item.inspiration_id
      ? `/w/${workspaceId}/inspirations/${item.inspiration_id}`
      : null;
  const primaryHref = inspirationHref ?? item.canonical_url;
  const primaryIsExternal = inspirationHref === null;

  return (
    <article className="group min-w-0 overflow-hidden rounded-xl border border-border bg-surface shadow-panel transition duration-200 hover:-translate-y-0.5 hover:border-primary-300 hover:shadow-popover">
      <Link
        className="block"
        href={primaryHref}
        rel={primaryIsExternal ? "noreferrer" : undefined}
        target={primaryIsExternal ? "_blank" : undefined}
      >
        <div
          className={`relative aspect-[16/9] overflow-hidden bg-gradient-to-br ${gradients[item.platform] ?? "from-primary-700 via-primary-500 to-cyan-400"}`}
        >
          {item.cover_url ? (
            // Provider cover hosts vary, so this intentionally stays a native image.
            // eslint-disable-next-line @next/next/no-img-element
            <img
              alt=""
              className="absolute inset-0 size-full object-cover transition duration-300 group-hover:scale-[1.03]"
              decoding="async"
              loading="lazy"
              onError={(event) => {
                event.currentTarget.style.display = "none";
              }}
              referrerPolicy="no-referrer"
              src={item.cover_url}
            />
          ) : (
            <div className="absolute inset-0 grid place-items-center text-white/85">
              {isVideo(item.content_type) ? (
                <span className="grid size-12 place-items-center rounded-full bg-black/20 backdrop-blur-sm">
                  <Play aria-hidden="true" className="ml-0.5" size={20} />
                </span>
              ) : (
                <ImageIcon aria-hidden="true" size={30} strokeWidth={1.6} />
              )}
            </div>
          )}
          <div
            aria-hidden="true"
            className="absolute inset-0 bg-gradient-to-t from-black/55 via-transparent to-black/10"
          />
          <div className="absolute inset-x-3 top-3 flex items-start justify-between gap-3">
            <span className="rounded-md bg-black/35 px-2 py-1 text-[11px] font-medium text-white backdrop-blur-sm">
              {platformLabel(item.platform)} · {contentTypeLabel(item.content_type)}
            </span>
            {grade ? (
              <span
                className={`rounded-md px-2.5 py-1 text-xs font-bold text-white shadow-sm ${grade.className}`}
              >
                {grade.label}
              </span>
            ) : null}
          </div>
          <ArrowUpRight
            aria-hidden="true"
            className="absolute right-3 bottom-3 text-white opacity-80 transition group-hover:translate-x-0.5 group-hover:-translate-y-0.5 group-hover:opacity-100"
            size={17}
          />
        </div>
      </Link>

      <div className="p-4">
        <Link
          className="line-clamp-2 min-h-12 text-base font-semibold leading-6 hover:text-primary-700"
          href={primaryHref}
          rel={primaryIsExternal ? "noreferrer" : undefined}
          target={primaryIsExternal ? "_blank" : undefined}
        >
          {item.title?.trim() || "未命名内容"}
        </Link>
        <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-text-muted">
          <span className="inline-flex items-center gap-1.5">
            <Calendar aria-hidden="true" size={13} />
            {formatPublishedDate(item.published_at)}
          </span>
          {item.latest_metrics?.views != null ? (
            <span
              aria-label={`播放或浏览 ${formatCompactNumber(item.latest_metrics.views)}`}
              className="inline-flex items-center gap-1.5"
            >
              <Eye aria-hidden="true" size={13} />
              {formatCompactNumber(item.latest_metrics.views)}
            </span>
          ) : null}
          {engagement != null ? (
            <span
              aria-label={`互动 ${formatCompactNumber(engagement)}`}
              className="inline-flex items-center gap-1.5"
            >
              <MessageCircle aria-hidden="true" size={13} />
              {formatCompactNumber(engagement)}
            </span>
          ) : null}
        </div>
        {inspirationHref ? (
          <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-xs">
            <span className="font-medium text-primary-700">已收录灵感 · 点击卡片查看分析</span>
            <a
              className="inline-flex items-center gap-1 text-text-muted hover:text-text"
              href={item.canonical_url}
              rel="noreferrer"
              target="_blank"
            >
              查看原文
              <ArrowUpRight aria-hidden="true" size={12} />
            </a>
          </div>
        ) : null}
        {item.latest_metrics ? (
          <p className="mt-2 text-[11px] text-text-muted">
            指标更新 {formatRelativeTime(item.latest_metrics.captured_at)}
          </p>
        ) : null}
      </div>
    </article>
  );
}

export function engagementTotal(
  metrics: TrackedProfileOverviewContent["latest_metrics"],
) {
  if (!metrics) return null;
  const values = [
    metrics.likes,
    metrics.comments,
    metrics.favorites,
    metrics.shares,
    metrics.downloads,
  ].filter((value): value is number => value != null);
  return values.length ? values.reduce((sum, value) => sum + value, 0) : null;
}

export function gradeLabel(grade: string | null | undefined) {
  const normalized = grade?.toLowerCase();
  return (
    {
      t1: { label: "T1", className: "bg-grade-t1" },
      t2: { label: "T2", className: "bg-grade-t2" },
      t3: { label: "T3", className: "bg-grade-t3" },
      qualified: { label: "已过门槛", className: "bg-primary-600" },
    }[normalized ?? ""] ?? null
  );
}

export function isVideo(contentType: string) {
  return contentType.toLowerCase() === "video";
}

function contentTypeLabel(contentType: string) {
  return (
    {
      note: "图文",
      image: "图文",
      image_text: "图文",
      photo: "图文",
      video: "视频",
      article: "文章",
      tweet: "帖子",
    }[contentType.toLowerCase()] ?? "内容"
  );
}

function formatPublishedDate(value: string | null) {
  if (!value) return "发布时间未知";
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date(value));
}
