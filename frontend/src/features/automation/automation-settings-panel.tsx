"use client";

import { Bot, CheckCircle2, LoaderCircle, Radar, Save } from "lucide-react";
import { useState } from "react";
import { ErrorState } from "@/src/components/ui/error-state";
import {
  useAutomationSettings,
  useUpdateAutomationSettings,
} from "@/src/features/automation/queries";
import type {
  AutomationMetricThresholds,
  AutomationSettings,
} from "@/src/features/automation/types";
import {
  InlineError,
  inputClass,
  primaryButton,
} from "@/src/features/production/ui";

const metricFields: Array<{
  key: keyof AutomationMetricThresholds;
  label: string;
  helper: string;
}> = [
  { key: "views", label: "浏览", helper: "播放或阅读数" },
  { key: "likes", label: "点赞", helper: "公开点赞数" },
  { key: "comments", label: "评论", helper: "公开评论数" },
  { key: "favorites", label: "收藏", helper: "公开收藏数" },
  { key: "shares", label: "分享", helper: "公开转发数" },
];

export function AutomationSettingsPanel({
  workspaceId,
  canManage,
}: {
  workspaceId: string;
  canManage: boolean;
}) {
  const settings = useAutomationSettings(workspaceId);

  if (settings.isLoading) {
    return <div className="h-80 animate-pulse rounded-xl bg-surface" />;
  }
  if (settings.error || !settings.data) {
    return (
      <section className="rounded-xl border border-border bg-surface shadow-panel">
        <ErrorState
          message={
            (settings.error as { message?: string })?.message ??
            "自动发现设置暂时无法读取。"
          }
          onRetry={() => settings.refetch()}
          requestId={(settings.error as { requestId?: string })?.requestId}
        />
      </section>
    );
  }

  return (
    <AutomationSettingsForm
      canManage={canManage}
      initial={settings.data}
      workspaceId={workspaceId}
    />
  );
}

function AutomationSettingsForm({
  workspaceId,
  canManage,
  initial,
}: {
  workspaceId: string;
  canManage: boolean;
  initial: AutomationSettings;
}) {
  const [form, setForm] = useState(initial);
  const [saved, setSaved] = useState(false);
  const update = useUpdateAutomationSettings(workspaceId);

  function setNumber(
    key: keyof Pick<
      AutomationSettings,
      | "scan_interval_hours"
      | "observation_hours"
      | "minimum_age_minutes"
      | "daily_l1_limit"
      | "daily_l2_limit"
    >,
    value: string,
  ) {
    setSaved(false);
    setForm((current) => ({ ...current, [key]: Math.max(0, Number(value)) }));
  }

  return (
    <section className="rounded-xl border border-border bg-surface shadow-panel">
      <div className="flex flex-col gap-3 border-b border-border p-5 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex items-start gap-3">
          <span className="rounded-lg bg-primary-50 p-2 text-primary-600">
            <Radar aria-hidden="true" size={18} />
          </span>
          <div>
            <h2 className="font-semibold">自动发现与分析</h2>
            <p className="mt-1 max-w-2xl text-xs leading-5 text-text-muted">
              定时扫描对标账号。内容先经过零 AI 成本的硬门槛，未达标只进入观察池；达到门槛后才会排队调用 AI。
            </p>
          </div>
        </div>
        <button
          aria-pressed={form.enabled}
          className={`rounded-full px-3 py-1.5 text-xs font-medium ${
            form.enabled
              ? "bg-success/10 text-success"
              : "bg-surface-subtle text-text-muted"
          }`}
          disabled={!canManage}
          onClick={() => {
            setSaved(false);
            setForm((current) => ({ ...current, enabled: !current.enabled }));
          }}
          type="button"
        >
          {form.enabled ? "自动化已开启" : "自动化已暂停"}
        </button>
      </div>

      <fieldset className="space-y-5 p-5" disabled={!canManage || update.isPending}>
        <div>
          <h3 className="text-sm font-semibold">扫描与观察</h3>
          <div className="mt-3 grid gap-3 sm:grid-cols-3">
            <NumberField
              helper="建议 24 小时"
              label="扫描间隔（小时）"
              max={720}
              min={1}
              onChange={(value) => setNumber("scan_interval_hours", value)}
              value={form.scan_interval_hours}
            />
            <NumberField
              helper="未达标内容继续刷新"
              label="观察窗口（小时）"
              max={720}
              min={1}
              onChange={(value) => setNumber("observation_hours", value)}
              value={form.observation_hours}
            />
            <NumberField
              helper="避免刚发布就误判"
              label="最短观察（分钟）"
              max={43_200}
              min={0}
              onChange={(value) => setNumber("minimum_age_minutes", value)}
              value={form.minimum_age_minutes}
            />
          </div>
        </div>

        <div className="h-px bg-border" />

        <div>
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <h3 className="text-sm font-semibold">内容硬门槛</h3>
              <p className="mt-1 text-xs leading-5 text-text-muted">
                指标检查由规则引擎完成，不调用 AI。阈值为 0 表示不启用该指标；“全部达标”仅检查已启用指标。
              </p>
            </div>
            <select
              aria-label="门槛匹配方式"
              className={inputClass}
              onChange={(event) => {
                setSaved(false);
                setForm((current) => ({
                  ...current,
                  threshold_match: event.target.value as "any" | "all",
                }));
              }}
              value={form.threshold_match}
            >
              <option value="any">任一指标达标</option>
              <option value="all">全部指标达标</option>
            </select>
          </div>
          <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
            {metricFields.map((field) => (
              <NumberField
                helper={field.helper}
                key={field.key}
                label={field.label}
                max={10_000_000_000}
                min={0}
                onChange={(value) => {
                  setSaved(false);
                  setForm((current) => ({
                    ...current,
                    metric_thresholds: {
                      ...current.metric_thresholds,
                      [field.key]: Math.max(0, Number(value)),
                    },
                  }));
                }}
                value={form.metric_thresholds[field.key]}
              />
            ))}
          </div>
        </div>

        <div className="h-px bg-border" />

        <div>
          <h3 className="flex items-center gap-2 text-sm font-semibold">
            <Bot className="text-primary-600" size={16} /> AI 分层分析
          </h3>
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            <AnalysisControl
              checked={form.auto_l1}
              description="仅对通过硬门槛的内容运行快速分析"
              label="自动运行 L1"
              limit={form.daily_l1_limit}
              maxLimit={10_000}
              onCheckedChange={(checked) => {
                setSaved(false);
                setForm((current) => ({ ...current, auto_l1: checked }));
              }}
              onLimitChange={(value) => setNumber("daily_l1_limit", value)}
            />
            <AnalysisControl
              checked={form.auto_l2}
              description="仅对 L1 推荐深挖的候选运行深度分析"
              label="自动运行 L2"
              limit={form.daily_l2_limit}
              maxLimit={10_000}
              onCheckedChange={(checked) => {
                setSaved(false);
                setForm((current) => ({ ...current, auto_l2: checked }));
              }}
              onLimitChange={(value) => setNumber("daily_l2_limit", value)}
            />
          </div>
        </div>

        {!canManage ? (
          <p className="rounded-lg bg-surface-subtle p-3 text-xs text-text-muted">
            当前角色可查看自动化规则，只有 Owner 可以修改。
          </p>
        ) : null}
        <InlineError error={update.error} />
        <div className="flex items-center gap-3">
          {canManage ? (
            <button
              className={primaryButton}
              onClick={() => {
                setSaved(false);
                update.mutate(form, { onSuccess: () => setSaved(true) });
              }}
              type="button"
            >
              {update.isPending ? (
                <LoaderCircle className="animate-spin" size={15} />
              ) : (
                <Save size={15} />
              )}
              保存自动化设置
            </button>
          ) : null}
          {saved ? (
            <span className="flex items-center gap-1.5 text-xs text-success">
              <CheckCircle2 size={14} /> 已保存
            </span>
          ) : null}
        </div>
      </fieldset>
    </section>
  );
}

function NumberField({
  label,
  helper,
  value,
  min,
  max,
  onChange,
}: {
  label: string;
  helper: string;
  value: number;
  min: number;
  max?: number;
  onChange: (value: string) => void;
}) {
  return (
    <label className="block">
      <span className="text-xs font-medium">{label}</span>
      <input
        className={`${inputClass} mt-1 w-full`}
        min={min}
        max={max}
        onChange={(event) => onChange(event.target.value)}
        type="number"
        value={value}
      />
      <span className="mt-1 block text-[11px] text-text-muted">{helper}</span>
    </label>
  );
}

function AnalysisControl({
  label,
  description,
  checked,
  limit,
  maxLimit,
  onCheckedChange,
  onLimitChange,
}: {
  label: string;
  description: string;
  checked: boolean;
  limit: number;
  maxLimit: number;
  onCheckedChange: (checked: boolean) => void;
  onLimitChange: (value: string) => void;
}) {
  return (
    <div className="rounded-lg border border-border p-4">
      <label className="flex items-start gap-3">
        <input
          checked={checked}
          className="mt-0.5 size-4 accent-[var(--color-primary-600)]"
          onChange={(event) => onCheckedChange(event.target.checked)}
          type="checkbox"
        />
        <span>
          <strong className="block text-sm">{label}</strong>
          <span className="mt-1 block text-xs leading-5 text-text-muted">
            {description}
          </span>
        </span>
      </label>
      <label className="mt-3 flex items-center justify-between gap-3 text-xs">
        每日最多
        <input
          className={`${inputClass} w-24`}
          disabled={!checked}
          min={0}
          max={maxLimit}
          onChange={(event) => onLimitChange(event.target.value)}
          type="number"
          value={limit}
        />
      </label>
    </div>
  );
}
