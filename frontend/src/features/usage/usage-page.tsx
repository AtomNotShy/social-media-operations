"use client";

import {
  Activity,
  BadgeDollarSign,
  CheckCircle2,
  CircleDollarSign,
  Database,
  ShieldAlert,
} from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { ErrorState } from "@/src/components/ui/error-state";
import { PageHeader } from "@/src/components/ui/page-header";
import { useWorkspaces } from "@/src/features/identity/queries";
import {
  useAIUsage,
  useASRUsage,
  useProviderUsage,
} from "@/src/features/usage/queries";

const ranges = [
  { label: "近 7 天", value: "7d", days: 7 },
  { label: "近 30 天", value: "30d", days: 30 },
  { label: "本月", value: "month", days: 0 },
];

export function UsagePage({ workspaceId }: { workspaceId: string }) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const range = searchParams.get("range") ?? "7d";
  const { dateFrom, dateTo } = dateRange(range);
  const usage = useProviderUsage(workspaceId, dateFrom, dateTo);
  const ai = useAIUsage(workspaceId, dateFrom, dateTo);
  const asr = useASRUsage(workspaceId, dateFrom, dateTo);
  const workspaces = useWorkspaces(workspaceId !== "demo");
  const workspace = workspaces.data?.find((item) => item.id === workspaceId);
  const dailyBudget =
    workspaceId === "demo"
      ? 5
      : Number(workspace?.daily_provider_budget_usd ?? 0);
  const today = new Date().toISOString().slice(0, 10);
  const aiToday = useAIUsage(workspaceId, today, today);
  const todayCost = usage.data?.items
    .filter((item) => item.usage_date === today)
    .reduce((sum, item) => sum + Number(item.estimated_cost_usd), 0) ?? 0;
  const budgetRatio = dailyBudget > 0 ? (todayCost / dailyBudget) * 100 : 0;
  const dailyAIBudget =
    workspaceId === "demo" ? 5 : Number(workspace?.daily_ai_budget_usd ?? 0);
  const aiBudgetRatio =
    dailyAIBudget > 0
      ? (Number(aiToday.data?.cost_usd ?? 0) / dailyAIBudget) * 100
      : 0;
  const successRate = usage.data?.request_count
    ? (usage.data.success_count / usage.data.request_count) * 100
    : 0;

  function setRange(value: string) {
    router.replace(`/w/${workspaceId}/usage?range=${value}`);
  }

  return (
    <>
      <PageHeader
        eyebrow="系统"
        title="用量与费用"
        description="查看外部数据调用的真实计数、服务端估算费用与工作区预算使用情况。"
      />

      <div className="mb-5 flex flex-wrap gap-2">
        {ranges.map((item) => (
          <button
            className={`rounded-full border px-3.5 py-2 text-xs font-medium ${
              range === item.value
                ? "border-text bg-text text-white"
                : "border-border bg-surface text-text-muted"
            }`}
            key={item.value}
            onClick={() => setRange(item.value)}
            type="button"
          >
            {item.label}
          </button>
        ))}
      </div>

      {budgetRatio >= 70 ? (
        <BudgetNotice label="外部调用" ratio={budgetRatio} />
      ) : null}
      {aiBudgetRatio >= 70 ? (
        <BudgetNotice label="AI" ratio={aiBudgetRatio} />
      ) : null}

      {usage.isLoading ? (
        <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
          {Array.from({ length: 4 }).map((_, index) => (
            <div className="h-28 animate-pulse rounded-xl bg-surface" key={index} />
          ))}
        </div>
      ) : usage.error ? (
        <section className="rounded-xl border border-border bg-surface">
          <ErrorState
            message={
              (usage.error as { message?: string }).message ??
              "费用汇总暂时不可用，站内历史内容仍可浏览。"
            }
            onRetry={() => usage.refetch()}
            requestId={(usage.error as { requestId?: string }).requestId}
          />
        </section>
      ) : usage.data ? (
        <>
          <section className="mb-5 grid grid-cols-2 gap-3 xl:grid-cols-4">
            <Summary
              icon={CircleDollarSign}
              label="服务端估算费用"
              value={`US$${Number(usage.data.estimated_cost_usd).toFixed(2)}`}
              detail={`${dateFrom} 至 ${dateTo}`}
            />
            <Summary
              icon={Activity}
              label="请求数"
              value={String(usage.data.request_count)}
              detail={`成功率 ${successRate.toFixed(1)}%`}
            />
            <Summary
              icon={BadgeDollarSign}
              label="计费请求"
              value={String(usage.data.billable_count)}
              detail="以供应商账本为准"
            />
            <Summary
              icon={Database}
              label="今日预算"
              value={
                dailyBudget > 0
                  ? `${Math.min(budgetRatio, 999).toFixed(0)}%`
                  : "未设置"
              }
              detail={
                dailyBudget > 0
                  ? `US$${todayCost.toFixed(2)} / US$${dailyBudget.toFixed(2)}`
                  : "请由 Owner 配置"
              }
            />
          </section>

          <section className="mb-5 overflow-hidden rounded-xl border border-border bg-surface shadow-panel">
            <div className="border-b border-border p-5">
              <h2 className="font-semibold">按日与端点明细</h2>
              <p className="mt-1 text-xs text-text-muted">
                费用为后端依据当前供应商定价记录的估算值，不由前端重新计算。
              </p>
            </div>
            {usage.data.items.length ? (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[760px] text-left text-sm">
                  <thead className="bg-canvas/70 text-xs text-text-muted">
                    <tr>
                      <th className="px-5 py-3 font-medium">日期</th>
                      <th className="px-4 py-3 font-medium">Provider</th>
                      <th className="px-4 py-3 font-medium">端点</th>
                      <th className="px-4 py-3 text-right font-medium">请求</th>
                      <th className="px-4 py-3 text-right font-medium">成功</th>
                      <th className="px-4 py-3 text-right font-medium">计费</th>
                      <th className="px-5 py-3 text-right font-medium">估算费用</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {usage.data.items.map((item) => (
                      <tr key={`${item.usage_date}:${item.provider}:${item.endpoint_key}`}>
                        <td className="px-5 py-3.5 tabular-nums">{item.usage_date}</td>
                        <td className="px-4 py-3.5">{item.provider}</td>
                        <td className="px-4 py-3.5 font-mono text-xs">{item.endpoint_key}</td>
                        <td className="px-4 py-3.5 text-right tabular-nums">{item.request_count}</td>
                        <td className="px-4 py-3.5 text-right tabular-nums">{item.success_count}</td>
                        <td className="px-4 py-3.5 text-right tabular-nums">{item.billable_count}</td>
                        <td className="px-5 py-3.5 text-right font-medium tabular-nums">
                          US${Number(item.estimated_cost_usd).toFixed(4)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="p-10 text-center">
                <CheckCircle2 aria-hidden="true" className="mx-auto text-success" size={26} />
                <h3 className="mt-3 font-semibold">这个时间范围没有供应商调用</h3>
                <p className="mt-2 text-sm text-text-muted">站内浏览不会产生外部数据调用费用。</p>
              </div>
            )}
          </section>

          <section className="grid gap-4 md:grid-cols-3">
            <LedgerCard
              detail={
                ai.data
                  ? `成功 ${ai.data.success_count}/${ai.data.run_count} · 输入 ${ai.data.input_tokens.toLocaleString()} / 输出 ${ai.data.output_tokens.toLocaleString()} Token`
                  : ai.error
                    ? "AI 用量暂时读取失败"
                    : "正在读取 AI 用量"
              }
              title="AI 分析"
              value={
                ai.data ? `US$${Number(ai.data.cost_usd).toFixed(4)}` : "—"
              }
            />
            <LedgerCard
              detail={
                asr.data
                  ? `成功 ${asr.data.success_count}/${asr.data.transcript_count} · ${formatDuration(asr.data.audio_duration_ms)} 音频`
                  : asr.error
                    ? "ASR 用量暂时读取失败"
                    : "正在读取 ASR 用量"
              }
              title="语音转写"
              value={
                asr.data ? `US$${Number(asr.data.cost_usd).toFixed(4)}` : "—"
              }
            />
            <Availability
              description="当前接口未聚合缓存命中次数，不根据请求差额推测命中率。"
              title="缓存命中"
            />
          </section>
        </>
      ) : null}
    </>
  );
}

function dateRange(range: string) {
  const now = new Date();
  const to = now.toISOString().slice(0, 10);
  const from = new Date(now);
  if (range === "month") from.setDate(1);
  else from.setDate(from.getDate() - (range === "30d" ? 29 : 6));
  return { dateFrom: from.toISOString().slice(0, 10), dateTo: to };
}

function Summary({
  icon: Icon,
  label,
  value,
  detail,
}: {
  icon: typeof Activity;
  label: string;
  value: string;
  detail: string;
}) {
  return (
    <div className="rounded-xl border border-border bg-surface p-4 shadow-panel sm:p-5">
      <div className="flex items-center gap-2 text-xs text-text-muted">
        <Icon aria-hidden="true" size={15} />
        {label}
      </div>
      <strong className="mt-3 block text-2xl font-semibold tabular-nums">{value}</strong>
      <p className="mt-1 text-[11px] text-text-muted">{detail}</p>
    </div>
  );
}

function BudgetNotice({ ratio, label }: { ratio: number; label: string }) {
  const stopped = ratio >= 100;
  return (
    <div
      className={`mb-5 flex items-start gap-3 rounded-xl border p-4 ${
        stopped
          ? "border-red-200 bg-red-50 text-red-800"
          : "border-amber-200 bg-amber-50 text-amber-900"
      }`}
    >
      <ShieldAlert aria-hidden="true" className="mt-0.5 shrink-0" size={18} />
      <div>
        <p className="text-sm font-semibold">
          {stopped
            ? `今日${label}预算已用尽`
            : `今日${label}预算已使用 ${ratio.toFixed(0)}%`}
        </p>
        <p className="mt-1 text-xs leading-5">
          {stopped
            ? "新的搜索、抓取和详情增强会被后端阻止；已入库内容、分析记录与站内编辑仍可使用。"
            : "接近预算上限，请确认高成本搜索范围。达到 100% 后只有新的外部调用会停止。"}
        </p>
      </div>
    </div>
  );
}

function Availability({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <div className="rounded-xl border border-dashed border-border bg-surface/70 p-5">
      <p className="text-sm font-semibold">{title}</p>
      <p className="mt-2 text-xs leading-5 text-text-muted">{description}</p>
    </div>
  );
}

function LedgerCard({
  title,
  value,
  detail,
}: {
  title: string;
  value: string;
  detail: string;
}) {
  return (
    <div className="rounded-xl border border-border bg-surface p-5 shadow-panel">
      <p className="text-sm font-semibold">{title}</p>
      <strong className="mt-3 block text-xl font-semibold tabular-nums">{value}</strong>
      <p className="mt-2 text-xs leading-5 text-text-muted">{detail}</p>
    </div>
  );
}

function formatDuration(milliseconds: number) {
  const minutes = Math.floor(milliseconds / 60_000);
  const seconds = Math.floor((milliseconds % 60_000) / 1000);
  return `${minutes}分${seconds}秒`;
}
