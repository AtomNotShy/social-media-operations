import { createElement } from "react";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import {
  engagementTotal,
  gradeLabel,
  ProfileOverviewContentCard,
} from "./profile-overview-content-card";
import type { TrackedProfileOverviewContent } from "./types";

const baseContent: TrackedProfileOverviewContent = {
  id: "91d3e8c2-776d-430c-8e42-1df65efcc001",
  platform: "xiaohongshu",
  external_id: "xhs-growth-01",
  canonical_url: "https://www.xiaohongshu.com/explore/demo-growth",
  content_type: "note",
  title: "把品牌内容拆成三条可复用的增长线",
  cover_url: null,
  published_at: "2026-07-30T10:00:00.000Z",
  first_seen_at: "2026-07-30T10:05:00.000Z",
  latest_metrics: null,
  latest_score: null,
  in_inspiration_library: false,
  inspiration_id: null,
};

describe("ProfileOverviewContentCard", () => {
  afterEach(cleanup);

  it("shows available grade and metric evidence", () => {
    render(
      createElement(ProfileOverviewContentCard, {
        item: {
          ...baseContent,
          latest_score: {
            calculated_at: "2026-07-31T10:00:00.000Z",
            grade: "t1",
            tier: "A",
            r_value: "5.74",
            m_value: "0.81",
          },
          latest_metrics: {
            captured_at: "2026-07-31T10:00:00.000Z",
            views: 12800,
            likes: 120,
            comments: 8,
            favorites: null,
            shares: 2,
            downloads: null,
          },
          in_inspiration_library: true,
          inspiration_id: "a11d18b5-aeb6-4fc1-a146-1c1cd843a001",
        },
        workspaceId: "demo",
      }),
    );

    expect(screen.getByText("T1")).toBeTruthy();
    expect(screen.getByLabelText("播放或浏览 1.3万")).toBeTruthy();
    expect(screen.getByLabelText("互动 130")).toBeTruthy();
    expect(
      screen
        .getByRole("link", {
          name: "把品牌内容拆成三条可复用的增长线",
        })
        .getAttribute("href"),
    ).toBe(
      "/w/demo/inspirations/a11d18b5-aeb6-4fc1-a146-1c1cd843a001",
    );
  });

  it("does not turn missing metrics into zero", () => {
    render(
      createElement(ProfileOverviewContentCard, {
        item: baseContent,
        workspaceId: "demo",
      }),
    );

    expect(screen.queryByLabelText(/^播放或浏览 /)).toBeNull();
    expect(screen.queryByLabelText(/^互动 /)).toBeNull();
    expect(screen.queryByText(/^T[123]$/)).toBeNull();
  });
});

describe("profile overview evidence helpers", () => {
  it("only totals known interaction fields", () => {
    expect(
      engagementTotal({
        captured_at: "2026-07-31T10:00:00.000Z",
        views: null,
        likes: null,
        comments: null,
        favorites: null,
        shares: null,
        downloads: null,
      }),
    ).toBeNull();
    expect(
      engagementTotal({
        captured_at: "2026-07-31T10:00:00.000Z",
        views: null,
        likes: 0,
        comments: null,
        favorites: null,
        shares: null,
        downloads: null,
      }),
    ).toBe(0);
  });

  it("only labels supported business grades", () => {
    expect(gradeLabel("T2")?.label).toBe("T2");
    expect(gradeLabel("qualified")?.label).toBe("已过门槛");
    expect(gradeLabel("normal")).toBeNull();
    expect(gradeLabel(null)).toBeNull();
  });
});
