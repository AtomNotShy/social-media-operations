"use client";

import { ArrowUpRight, FileBarChart, TrendingUp } from "lucide-react";
import Link from "next/link";
import type { PerformanceDashboard } from "@/src/features/production/types";
import { formatCompactNumber, platformLabel } from "@/src/lib/format";

export type PerformanceRecord = PerformanceDashboard["records"][number];

export function PlatformMark({
  platform,
  size = "md",
}: {
  platform: string;
  size?: "sm" | "md" | "lg";
}) {
  const sizeClass =
    size === "lg" ? "size-14 text-base" : size === "sm" ? "size-8 text-[11px]" : "size-10 text-xs";
  const theme =
    platform === "xiaohongshu"
      ? "bg-[#ff3154] text-white"
      : platform === "douyin"
        ? "bg-[#121317] text-white"
        : platform === "x"
          ? "bg-black text-white"
          : "bg-primary-50 text-primary-700";
  const label = platform === "xiaohongshu" ? "书" : platform === "douyin" ? "抖" : platform === "x" ? "X" : platformLabel(platform).slice(0, 1);

  return (
    <span
      aria-label={platformLabel(platform)}
      className={`grid shrink-0 place-items-center rounded-xl font-bold tracking-tight shadow-sm ${sizeClass} ${theme}`}
    >
      {label}
    </span>
  );
}

export function summarizePerformance(records: PerformanceRecord[]) {
  const totals = records.reduce(
    (result, item) => ({
      exposure: result.exposure + item.exposure,
      interactions: result.interactions + item.interactions,
      conversions: result.conversions + item.conversions,
    }),
    { exposure: 0, interactions: 0, conversions: 0 },
  );
  return {
    ...totals,
    published: records.length,
    engagementRate: totals.exposure ? totals.interactions / totals.exposure : 0,
    conversionRate: totals.exposure ? totals.conversions / totals.exposure : 0,
  };
}

export function formatRate(value: number) {
  return new Intl.NumberFormat("zh-CN", {
    style: "percent",
    minimumFractionDigits: 1,
    maximumFractionDigits: 2,
  }).format(value);
}

function metricNumber(metrics: Record<string, unknown>, key: string) {
  const value = metrics[key];
  return typeof value === "number" ? value : 0;
}

export function nativeMetric(record: PerformanceRecord) {
  const metrics = record.metrics as Record<string, unknown>;
  if (record.platform === "xiaohongshu") {
    return { label: "收藏", value: formatCompactNumber(metricNumber(metrics, "favorites")) };
  }
  if (record.platform === "douyin") {
    return {
      label: "完播率",
      value: formatRate(metricNumber(metrics, "completion_rate")),
    };
  }
  if (record.platform === "x") {
    return { label: "链接点击", value: formatCompactNumber(metricNumber(metrics, "link_clicks")) };
  }
  return { label: "互动", value: formatCompactNumber(record.interactions) };
}

export function PerformanceTrendChart({ records }: { records: PerformanceRecord[] }) {
  const points = [...records]
    .sort((a, b) => new Date(a.published_at).getTime() - new Date(b.published_at).getTime())
    .slice(-12);

  if (points.length < 2) {
    return (
      <div className="grid min-h-56 place-items-center rounded-xl bg-surface-subtle px-6 text-center">
        <div>
          <FileBarChart className="mx-auto text-text-muted" size={24} />
          <p className="mt-3 text-sm font-medium">还需要更多发布数据</p>
          <p className="mt-1 text-xs text-text-muted">当前时间范围至少有 2 条已复盘内容后会生成趋势。</p>
        </div>
      </div>
    );
  }

  const width = 760;
  const height = 240;
  const inset = { top: 24, right: 18, bottom: 38, left: 18 };
  const chartWidth = width - inset.left - inset.right;
  const chartHeight = height - inset.top - inset.bottom;
  const maxExposure = Math.max(...points.map((item) => item.exposure), 1);
  const maxInteractions = Math.max(...points.map((item) => item.interactions), 1);
  const coordinates = (key: "exposure" | "interactions", max: number) =>
    points
      .map((item, index) => {
        const x = inset.left + (index / (points.length - 1)) * chartWidth;
        const y = inset.top + (1 - item[key] / max) * chartHeight;
        return `${x.toFixed(1)},${y.toFixed(1)}`;
      })
      .join(" ");

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center gap-5 text-xs text-text-muted">
        <span className="flex items-center gap-2"><i className="size-2 rounded-full bg-primary-600" />曝光</span>
        <span className="flex items-center gap-2"><i className="size-2 rounded-full bg-violet-500" />互动</span>
        <span className="ml-auto text-[11px]">按每条内容的最新复盘窗口</span>
      </div>
      <svg aria-label="账号曝光与互动趋势" className="h-auto w-full overflow-visible" role="img" viewBox={`0 0 ${width} ${height}`}>
        {[0, 0.25, 0.5, 0.75, 1].map((value) => {
          const y = inset.top + value * chartHeight;
          return <line key={value} stroke="var(--color-border)" strokeDasharray="4 6" strokeWidth="1" x1={inset.left} x2={width - inset.right} y1={y} y2={y} />;
        })}
        <polyline fill="none" points={coordinates("exposure", maxExposure)} stroke="var(--color-primary-600)" strokeLinecap="round" strokeLinejoin="round" strokeWidth="3" />
        <polyline fill="none" points={coordinates("interactions", maxInteractions)} stroke="#8b5cf6" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" />
        {points.map((item, index) => {
          const x = inset.left + (index / (points.length - 1)) * chartWidth;
          const y = inset.top + (1 - item.exposure / maxExposure) * chartHeight;
          return <circle cx={x} cy={y} fill="white" key={item.publish_record_id} r="4" stroke="var(--color-primary-600)" strokeWidth="2.5" />;
        })}
        {points.map((item, index) => {
          if (points.length > 7 && index % 2 === 1 && index !== points.length - 1) return null;
          const x = inset.left + (index / (points.length - 1)) * chartWidth;
          return (
            <text fill="var(--color-text-muted)" fontSize="10" key={`label-${item.publish_record_id}`} textAnchor={index === 0 ? "start" : index === points.length - 1 ? "end" : "middle"} x={x} y={height - 10}>
              {new Date(item.published_at).toLocaleDateString("zh-CN", { month: "numeric", day: "numeric" })}
            </text>
          );
        })}
      </svg>
    </div>
  );
}

export function ContentPerformanceTable({
  records,
  workspaceId,
  limit,
}: {
  records: PerformanceRecord[];
  workspaceId: string;
  limit?: number;
}) {
  const items = [...records]
    .sort((a, b) => b.exposure - a.exposure)
    .slice(0, limit ?? records.length);

  if (!items.length) {
    return <p className="py-12 text-center text-sm text-text-muted">暂无已复盘的发布内容。</p>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[760px] border-collapse text-left">
        <thead>
          <tr className="border-b border-border text-[11px] font-medium text-text-muted">
            <th className="px-5 py-3 font-medium">内容</th>
            <th className="px-3 py-3 font-medium">曝光</th>
            <th className="px-3 py-3 font-medium">互动</th>
            <th className="px-3 py-3 font-medium">互动率</th>
            <th className="px-3 py-3 font-medium">平台指标</th>
            <th className="px-3 py-3 font-medium">转化</th>
            <th className="px-5 py-3 text-right font-medium">详情</th>
          </tr>
        </thead>
        <tbody>
          {items.map((record) => {
            const platformMetric = nativeMetric(record);
            return (
              <tr className="border-b border-border last:border-0 hover:bg-surface-subtle/70" key={record.publish_record_id}>
                <td className="max-w-80 px-5 py-4">
                  <p className="truncate text-sm font-medium">{record.content_title}</p>
                  <p className="mt-1 text-[11px] text-text-muted">{new Date(record.published_at).toLocaleDateString("zh-CN")} · {record.latest_review_window ?? "待复盘"}</p>
                </td>
                <td className="px-3 py-4 text-sm font-medium tabular-nums">{formatCompactNumber(record.exposure)}</td>
                <td className="px-3 py-4 text-sm tabular-nums">{formatCompactNumber(record.interactions)}</td>
                <td className="px-3 py-4 text-sm tabular-nums">{formatRate(record.exposure ? record.interactions / record.exposure : 0)}</td>
                <td className="px-3 py-4"><span className="text-[10px] text-text-muted">{platformMetric.label}</span><strong className="block text-sm tabular-nums">{platformMetric.value}</strong></td>
                <td className="px-3 py-4 text-sm tabular-nums">{record.conversions.toLocaleString()}</td>
                <td className="px-5 py-4 text-right">
                  <Link aria-label={`查看 ${record.content_title} 复盘`} className="inline-grid size-8 place-items-center rounded-lg text-text-muted hover:bg-primary-50 hover:text-primary-700" href={`/w/${workspaceId}/reviews/${record.publish_record_id}`}>
                    <ArrowUpRight size={15} />
                  </Link>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export function InsightList({ records, platform }: { records: PerformanceRecord[]; platform: string }) {
  const ranked = [...records].sort((a, b) => b.exposure - a.exposure);
  const best = ranked[0];
  const averageRate = summarizePerformance(records).engagementRate;
  const platformAdvice =
    platform === "xiaohongshu"
      ? "优先复用高收藏内容的标题结构，下一轮只测试封面变量。"
      : platform === "douyin"
        ? "把高完播内容的前 3 秒拆成模板，下一轮对照测试开场。"
        : "保留能带来链接点击的数据叙事，减少只有态度没有证据的帖子。";
  const insights = best
    ? [
        { title: "最强内容信号", detail: `「${best.content_title}」带来 ${formatCompactNumber(best.exposure)} 曝光。` },
        { title: "当前互动效率", detail: `选定窗口的平均互动率为 ${formatRate(averageRate)}。` },
        { title: "建议下个动作", detail: platformAdvice },
      ]
    : [{ title: "等待第一次复盘", detail: "发布后录入 24h 指标，这里会自动生成可执行建议。" }];

  return (
    <div className="space-y-1">
      {insights.map((item, index) => (
        <div className="flex gap-3 border-b border-border py-4 last:border-0" key={item.title}>
          <span className="mt-0.5 grid size-8 shrink-0 place-items-center rounded-lg bg-primary-50 text-primary-700">
            {index === insights.length - 1 ? <TrendingUp size={15} /> : <span className="text-xs font-semibold">{index + 1}</span>}
          </span>
          <div>
            <h3 className="text-sm font-semibold">{item.title}</h3>
            <p className="mt-1 text-xs leading-5 text-text-muted">{item.detail}</p>
          </div>
        </div>
      ))}
    </div>
  );
}
