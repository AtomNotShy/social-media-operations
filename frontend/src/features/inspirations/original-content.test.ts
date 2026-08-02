import { createElement } from "react";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import {
  hasTranscribableVideo,
  OriginalContent,
  parseOriginalContent,
} from "@/src/features/inspirations/original-content";
import type { ExternalContent } from "@/src/features/inspirations/types";

function content(overrides: Partial<ExternalContent>): ExternalContent {
  return {
    id: "content-1",
    platform: "xiaohongshu",
    external_id: "note-1",
    tracked_profile_id: null,
    canonical_url: "https://www.xiaohongshu.com/explore/note-1",
    content_type: "image_text",
    title: "标题",
    body_text: "正文",
    published_at: null,
    duration_ms: null,
    author_snapshot: {},
    media_manifest: [],
    original_content: null,
    detail_status: "detail",
    first_seen_at: "2026-08-01T00:00:00Z",
    last_seen_at: "2026-08-01T00:00:00Z",
    ...overrides,
  };
}

afterEach(cleanup);

describe("hasTranscribableVideo", () => {
  it("requires a video entry with a URL", () => {
    expect(
      hasTranscribableVideo([
        { type: "video", url: "https://media.example.invalid/video.mp4" },
      ]),
    ).toBe(true);
  });

  it("rejects text-only or image-only manifests", () => {
    expect(hasTranscribableVideo([])).toBe(false);
    expect(
      hasTranscribableVideo([
        { type: "image", url: "https://media.example.invalid/pic.jpg" },
      ]),
    ).toBe(false);
  });

  it("rejects video entries without a usable URL", () => {
    expect(hasTranscribableVideo([{ type: "video", url: "" }])).toBe(false);
    expect(hasTranscribableVideo([{ type: "video" }])).toBe(false);
  });
});

describe("parseOriginalContent", () => {
  it("parses structured XHS blocks and drops malformed entries", () => {
    const parsed = parseOriginalContent({
      format: "xhs",
      blocks: [
        { type: "heading", runs: [{ text: "小标题", style: "text" }] },
        {
          type: "paragraph",
          runs: [
            { text: "第一段 " },
            { text: "#灵感#", style: "hashtag" },
            { text: " @博主", style: "mention" },
            { text: "链接", style: "url", url: "https://example.com" },
          ],
        },
        { type: "image", url: "https://example.com/1.jpg" },
        { type: "video", url: "https://example.com/v.mp4", cover_url: null },
        { type: "divider" },
        { type: "unknown", runs: [] },
        { type: "image", url: "" },
      ],
    });

    expect(parsed).not.toBeNull();
    expect(parsed!.blocks.map((block) => block.type)).toEqual([
      "heading",
      "paragraph",
      "image",
      "video",
      "divider",
    ]);
  });

  it("returns null for missing or empty blocks", () => {
    expect(parseOriginalContent(null)).toBeNull();
    expect(parseOriginalContent({ format: "xhs", blocks: [] })).toBeNull();
    expect(parseOriginalContent({ format: "xhs", blocks: "nope" })).toBeNull();
  });
});

describe("OriginalContent", () => {
  it("renders XHS headings, styled hashtags, images and dividers", () => {
    render(
      createElement(OriginalContent, {
        content: content({
          original_content: {
            format: "xhs",
            blocks: [
              { type: "heading", runs: [{ text: "小标题" }] },
              {
                type: "paragraph",
                runs: [
                  { text: "正文段落 " },
                  { text: "#灵感#", style: "hashtag" },
                ],
              },
              { type: "image", url: "https://example.com/pic.jpg" },
              { type: "divider" },
            ],
          },
        }),
      }),
    );

    expect(screen.getByText("小标题")).toBeTruthy();
    expect(screen.getByText(/正文段落/)).toBeTruthy();
    expect(screen.getByText("#灵感#")).toBeTruthy();
    expect(screen.getByAltText("原内容图片")).toBeTruthy();
    expect(screen.getByRole("separator")).toBeTruthy();
  });

  it("renders X tweets with expanded links, placeholders and a quote card", () => {
    render(
      createElement(OriginalContent, {
        content: content({
          platform: "x",
          original_content: {
            format: "x",
            blocks: [
              {
                type: "paragraph",
                runs: [
                  { text: "看看 " },
                  {
                    text: "https://example.com/article",
                    style: "url",
                    url: "https://example.com/article",
                  },
                  { text: " " },
                  { text: "[图片]", style: "media_placeholder" },
                ],
              },
              { type: "image", url: "https://pbs.twimg.com/media/a.jpg" },
              {
                type: "quote",
                text: "被引用的推文",
                author: { display_name: "引用者", handle: "quoter" },
                url: "https://x.com/quoter/status/1",
                media_url: null,
              },
            ],
          },
        }),
      }),
    );

    const link = screen.getByRole("link", { name: "https://example.com/article" });
    expect(link.getAttribute("href")).toBe("https://example.com/article");
    expect(screen.getByText("[图片]")).toBeTruthy();
    expect(screen.getByText("被引用的推文")).toBeTruthy();
    expect(screen.getByText("引用者")).toBeTruthy();
    expect(screen.getByRole("link", { name: "查看引用" }).getAttribute("href")).toBe(
      "https://x.com/quoter/status/1",
    );
  });

  it("groups consecutive images into a grid", () => {
    render(
      createElement(OriginalContent, {
        content: content({
          original_content: {
            format: "xhs",
            blocks: [
              { type: "paragraph", runs: [{ text: "先看这里" }] },
              { type: "image", url: "https://example.com/1.jpg" },
              { type: "image", url: "https://example.com/2.jpg" },
              { type: "paragraph", runs: [{ text: "然后是结论" }] },
            ],
          },
        }),
      }),
    );

    expect(screen.getAllByAltText(/原内容图片/)).toHaveLength(2);
  });

  it("falls back to plain body text plus manifest media for older rows", () => {
    render(
      createElement(OriginalContent, {
        content: content({
          body_text: "旧数据只有正文，没有结构化内容。",
          media_manifest: [
            { type: "photo", url: "https://example.com/legacy.jpg" },
          ],
        }),
      }),
    );

    expect(screen.getByText("旧数据只有正文，没有结构化内容。")).toBeTruthy();
    expect(screen.getByAltText("内容媒体")).toBeTruthy();
  });

  it("shows the empty copy when neither text nor structured content exists", () => {
    render(
      createElement(OriginalContent, {
        content: content({ body_text: null }),
      }),
    );

    expect(screen.getByText("当前内容源未提供可读取的正文。")).toBeTruthy();
  });
});
