import { createElement, useState } from "react";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { ContentMetricSnapshot } from "@/src/features/inspirations/types";
import {
  InlineMetrics,
  MetricHistoryDrawer,
  TaskConfirmationDialog,
} from "./inspiration-detail-page";

const snapshots: ContentMetricSnapshot[] = [
  {
    id: "snapshot-1",
    external_content_id: "content-1",
    captured_at: "2026-08-01T08:00:00.000Z",
    views: 12_800,
    likes: 4_286,
    comments: 318,
    favorites: 1_204,
    shares: 562,
    downloads: null,
    metrics: {},
  },
];

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("task action confirmation", () => {
  it("uses an accessible product dialog without calling window.confirm", () => {
    const nativeConfirm = vi.spyOn(window, "confirm");
    const onConfirm = vi.fn();

    render(
      createElement(TaskConfirmationDialog, {
        action: "analysis-l2",
        onClose: vi.fn(),
        onConfirm,
      }),
    );

    expect(
      screen.getByRole("dialog", { name: "确认运行 L2 深度分析？" }),
    ).toBeTruthy();
    expect(screen.getByText(/后台 AI 任务/)).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "确认运行" }));

    expect(onConfirm).toHaveBeenCalledOnce();
    expect(nativeConfirm).not.toHaveBeenCalled();
  });

  it("closes on Escape", () => {
    const onClose = vi.fn();
    render(
      createElement(TaskConfirmationDialog, {
        action: "comments",
        onClose,
        onConfirm: vi.fn(),
      }),
    );

    fireEvent.keyDown(window, { key: "Escape" });
    expect(onClose).toHaveBeenCalledOnce();
  });
});

describe("metric history", () => {
  it("opens the history drawer from the inline title metrics", () => {
    function HistoryHarness() {
      const [open, setOpen] = useState(false);
      return createElement(
        "div",
        null,
        createElement(InlineMetrics, {
          isLoading: false,
          metrics: snapshots[0],
          onOpenHistory: () => setOpen(true),
          platform: "xiaohongshu",
        }),
        open
          ? createElement(MetricHistoryDrawer, {
              isLoading: false,
              metrics: snapshots,
              onClose: () => setOpen(false),
              platform: "xiaohongshu",
            })
          : null,
      );
    }

    render(createElement(HistoryHarness));
    expect(screen.queryByRole("dialog", { name: "历史指标" })).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "查看历史指标" }));

    const drawer = screen.getByRole("dialog", { name: "历史指标" });
    expect(drawer).toBeTruthy();
    expect(within(drawer).getByRole("columnheader", { name: "收藏" })).toBeTruthy();
    expect(within(drawer).getByText("4,286")).toBeTruthy();
  });

  it("uses X terminology in the history table", () => {
    render(
      createElement(MetricHistoryDrawer, {
        isLoading: false,
        metrics: snapshots,
        onClose: vi.fn(),
        platform: "x",
      }),
    );

    expect(screen.getByRole("columnheader", { name: "转推" })).toBeTruthy();
    expect(screen.queryByRole("columnheader", { name: "收藏" })).toBeNull();
  });
});
