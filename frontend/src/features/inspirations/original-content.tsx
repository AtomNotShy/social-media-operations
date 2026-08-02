"use client";

import { Film } from "lucide-react";
import { useMemo } from "react";
import type { ExternalContent } from "@/src/features/inspirations/types";

export type OriginalRun = {
  text: string;
  style?:
    | "text"
    | "url"
    | "media_placeholder"
    | "mention"
    | "hashtag"
    | "bold"
    | "italic";
  url?: string | null;
};

export type OriginalBlock =
  | { type: "paragraph"; runs?: OriginalRun[] }
  | { type: "heading"; runs?: OriginalRun[] }
  | { type: "image"; url: string }
  | {
      type: "video";
      url?: string;
      cover_url?: string | null;
      duration_ms?: number | null;
      animated?: boolean;
    }
  | {
      type: "quote";
      text: string;
      author?: {
        display_name?: string | null;
        handle?: string | null;
      } | null;
      url?: string | null;
      media_url?: string | null;
    }
  | { type: "divider" };

export type OriginalContent = {
  format: string;
  blocks: OriginalBlock[];
};

type MediaEntry = {
  type?: unknown;
  url?: unknown;
  cover_url?: unknown;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

export function parseOriginalContent(
  value: Record<string, unknown> | null | undefined,
): OriginalContent | null {
  if (!isRecord(value)) return null;
  const blocks = Array.isArray(value.blocks) ? value.blocks : null;
  if (!blocks) return null;
  const parsed: OriginalBlock[] = [];
  for (const raw of blocks) {
    if (!isRecord(raw)) continue;
    const type = typeof raw.type === "string" ? raw.type : "";
    if (type === "paragraph" || type === "heading") {
      const runs = Array.isArray(raw.runs)
        ? (raw.runs as unknown[])
            .filter(isRecord)
            .map((run) => ({
              text: typeof run.text === "string" ? run.text : "",
              style:
                typeof run.style === "string"
                  ? (run.style as OriginalRun["style"])
                  : undefined,
              url:
                typeof run.url === "string"
                  ? run.url
                  : run.url == null
                    ? null
                    : undefined,
            }))
            .filter((run) => run.text)
        : [];
      if (!runs.length) continue;
      parsed.push({ type, runs });
    } else if (type === "image") {
      if (typeof raw.url === "string" && raw.url) {
        parsed.push({ type: "image", url: raw.url });
      }
    } else if (type === "video") {
      if (typeof raw.url === "string" && raw.url) {
        parsed.push({
          type: "video",
          url: raw.url,
          cover_url:
            typeof raw.cover_url === "string" ? raw.cover_url : null,
          duration_ms:
            typeof raw.duration_ms === "number" ? raw.duration_ms : null,
          animated: raw.animated === true,
        });
      }
    } else if (type === "quote") {
      if (typeof raw.text === "string" && raw.text) {
        const author = isRecord(raw.author) ? raw.author : null;
        parsed.push({
          type: "quote",
          text: raw.text,
          author: author
            ? {
                display_name:
                  typeof author.display_name === "string"
                    ? author.display_name
                    : null,
                handle: typeof author.handle === "string" ? author.handle : null,
              }
            : null,
          url: typeof raw.url === "string" ? raw.url : null,
          media_url: typeof raw.media_url === "string" ? raw.media_url : null,
        });
      }
    } else if (type === "divider") {
      parsed.push({ type: "divider" });
    }
  }
  if (!parsed.length) return null;
  return {
    format: typeof value.format === "string" ? value.format : "",
    blocks: parsed,
  };
}

export function mediaEntries(manifest: unknown[]): MediaEntry[] {
  return manifest.filter((item): item is MediaEntry => isRecord(item));
}

export function hasTranscribableVideo(manifest: unknown[]): boolean {
  return mediaEntries(manifest).some(
    (entry) =>
      entry.type === "video" &&
      typeof entry.url === "string" &&
      entry.url.length > 0,
  );
}

function InlineRuns({ runs }: { runs: OriginalRun[] }) {
  return (
    <>
      {runs.map((run, index) => {
        switch (run.style) {
          case "url":
            return (
              <a
                className="break-all font-medium text-primary-700 hover:underline"
                href={run.url ?? undefined}
                key={index}
                rel="noreferrer"
                target="_blank"
              >
                {run.text}
              </a>
            );
          case "mention":
          case "hashtag":
            return (
              <span className="font-medium text-primary-700" key={index}>
                {run.text}
              </span>
            );
          case "bold":
            return <strong key={index}>{run.text}</strong>;
          case "italic":
            return <em key={index}>{run.text}</em>;
          case "media_placeholder":
            return (
              <span
                className="text-xs font-medium text-text-muted"
                key={index}
              >
                {run.text}
              </span>
            );
          default:
            return <span key={index}>{run.text}</span>;
        }
      })}
    </>
  );
}

function VideoBlock({ block }: { block: Extract<OriginalBlock, { type: "video" }> }) {
  if (block.cover_url) {
    return (
      <div className="relative mt-3 overflow-hidden rounded-lg border border-border">
        {/* Remote provider URLs are intentionally rendered with a native image so
            each source can supply its own host without Next image configuration. */}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          alt="视频封面"
          className="h-56 w-full object-cover sm:h-64"
          src={block.cover_url ?? ""}
        />
        <span className="absolute right-3 bottom-3 inline-flex items-center gap-1.5 rounded-full bg-text/70 px-2.5 py-1 text-xs font-medium text-white">
          <Film aria-hidden="true" size={13} />
          视频
        </span>
      </div>
    );
  }
  return (
    <video
      className="mt-3 max-h-72 w-full rounded-lg border border-border"
      controls
      preload="metadata"
      src={block.url ?? undefined}
    />
  );
}

function MediaGrid({ entries }: { entries: MediaEntry[] }) {
  const visuals = entries.filter((entry) => {
    const type = entry.type;
    if (type !== "photo" && type !== "image" && type !== "video" && type !== "animated_gif") {
      return false;
    }
    return typeof entry.url === "string" && entry.url;
  });
  if (!visuals.length) return null;
  return (
    <div
      className={`mt-3 grid gap-2 ${
        visuals.length === 1 ? "grid-cols-1" : "grid-cols-2"
      }`}
    >
      {visuals.map((entry, index) => (
        <div
          className="relative overflow-hidden rounded-lg border border-border"
          key={index}
        >
          {entry.type === "video" || entry.type === "animated_gif" ? (
            typeof entry.cover_url === "string" && entry.cover_url ? (
              /* eslint-disable-next-line @next/next/no-img-element */
              <img
                alt="视频封面"
                className="h-32 w-full object-cover sm:h-44"
                src={entry.cover_url}
              />
            ) : (
              <div className="grid h-32 w-full place-items-center bg-surface-subtle sm:h-44">
                <Film aria-hidden="true" className="text-text-muted" size={20} />
              </div>
            )
          ) : (
            /* Remote provider URLs are intentionally rendered with a native image so
                each source can supply its own host without Next image configuration. */
            /* eslint-disable-next-line @next/next/no-img-element */
            <img
              alt="内容媒体"
              className="h-32 w-full object-cover sm:h-44"
              src={String(entry.url)}
            />
          )}
          {entry.type === "video" || entry.type === "animated_gif" ? (
            <span className="absolute right-2 bottom-2 inline-flex items-center gap-1 rounded-full bg-text/70 px-2 py-0.5 text-[11px] font-medium text-white">
              <Film aria-hidden="true" size={11} />
              {entry.type === "animated_gif" ? "动图" : "视频"}
            </span>
          ) : null}
        </div>
      ))}
    </div>
  );
}

function QuoteBlock({
  block,
  coverUrl,
}: {
  block: Extract<OriginalBlock, { type: "quote" }>;
  coverUrl: string | null;
}) {
  const authorName = block.author?.display_name ?? block.author?.handle ?? "引用内容";
  return (
    <blockquote className="mt-3 rounded-r-lg border-l-4 border-primary-200 bg-canvas/70 py-3 pr-4 pl-4">
      <div className="flex items-start justify-between gap-3">
        <span className="text-xs font-medium text-text-muted">{authorName}</span>
        {block.url ? (
          <a
            className="shrink-0 text-xs text-primary-700 hover:underline"
            href={block.url}
            rel="noreferrer"
            target="_blank"
          >
            查看引用
          </a>
        ) : null}
      </div>
      <p className="mt-1.5 line-clamp-3 text-sm leading-6 whitespace-pre-line">
        {block.text}
      </p>
      {coverUrl ? (
        /* eslint-disable-next-line @next/next/no-img-element */
        <img
          alt="引用内容媒体"
          className="mt-2 h-24 w-full rounded-md border border-border object-cover"
          src={coverUrl}
        />
      ) : null}
    </blockquote>
  );
}

function BlockView({
  block,
  platform,
}: {
  block: OriginalBlock;
  platform: string;
}) {
  switch (block.type) {
    case "heading":
      return (
        <h3 className="mt-4 text-base font-semibold text-text first:mt-0">
          <InlineRuns runs={block.runs ?? []} />
        </h3>
      );
    case "paragraph":
      return (
        <p className="mt-3 text-sm leading-7 whitespace-pre-line text-text first:mt-0">
          <InlineRuns runs={block.runs ?? []} />
        </p>
      );
    case "image":
      return (
        <div className="mt-3 first:mt-0">
          {/* Remote provider URLs are intentionally rendered with a native image so
              each source can supply its own host without Next image configuration. */}
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            alt="原内容图片"
            className="max-h-72 w-auto max-w-full rounded-lg border border-border object-cover"
            src={block.url}
          />
        </div>
      );
    case "video":
      return <VideoBlock block={block} />;
    case "quote":
      return (
        <QuoteBlock
          block={block}
          coverUrl={platform === "x" ? block.media_url ?? null : null}
        />
      );
    case "divider":
      return <hr className="my-4 border-border" />;
    default:
      return null;
  }
}

function groupImageBlocks(
  blocks: OriginalBlock[],
): Array<OriginalBlock | { type: "image_grid"; urls: string[] }> {
  const groups: Array<OriginalBlock | { type: "image_grid"; urls: string[] }> = [];
  let pending: string[] = [];
  const flush = () => {
    if (pending.length) {
      groups.push({ type: "image_grid", urls: pending });
      pending = [];
    }
  };
  for (const block of blocks) {
    if (block.type === "image") {
      pending.push(block.url);
    } else {
      flush();
      groups.push(block);
    }
  }
  flush();
  return groups;
}

function ImageGrid({ urls }: { urls: string[] }) {
  if (urls.length === 1) {
    return (
      <div className="mt-3 first:mt-0">
        {/* Remote provider URLs are intentionally rendered with a native image so
            each source can supply its own host without Next image configuration. */}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          alt="原内容图片"
          className="max-h-72 w-auto max-w-full rounded-lg border border-border object-cover"
          src={urls[0]}
        />
      </div>
    );
  }
  return (
    <div className="mt-3 grid grid-cols-2 gap-2 first:mt-0">
      {urls.map((url, index) => (
        /* Remote provider URLs are intentionally rendered with a native image so
            each source can supply its own host without Next image configuration. */
        /* eslint-disable-next-line @next/next/no-img-element */
        <img
          alt={`原内容图片 ${index + 1}`}
          className="h-40 w-full rounded-lg border border-border object-cover sm:h-52"
          key={url}
          src={url}
        />
      ))}
    </div>
  );
}

export function OriginalContent({
  content,
}: {
  content: ExternalContent;
}) {
  const original = useMemo(
    () => parseOriginalContent(content.original_content),
    [content.original_content],
  );
  const manifest = useMemo(
    () => mediaEntries(content.media_manifest ?? []),
    [content.media_manifest],
  );
  const bodyFallback = content.body_text || "当前内容源未提供可读取的正文。";

  if (!original) {
    return (
      <div>
        <p className="text-sm leading-7 whitespace-pre-line text-text">
          {bodyFallback}
        </p>
        <MediaGrid entries={manifest} />
      </div>
    );
  }

  return (
    <div>
      {groupImageBlocks(original.blocks).map((block, index) =>
        block.type === "image_grid" ? (
          <ImageGrid key={index} urls={block.urls} />
        ) : (
          <BlockView
            block={block}
            key={index}
            platform={content.platform}
          />
        ),
      )}
    </div>
  );
}
