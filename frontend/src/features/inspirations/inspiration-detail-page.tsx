"use client";

import {
  Archive,
  ArrowLeft,
  Bot,
  Check,
  ExternalLink,
  FileAudio,
  Gauge,
  LoaderCircle,
  MessageCircle,
  RefreshCw,
  RotateCcw,
  Sparkles,
  Tags,
} from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { ErrorState } from "@/src/components/ui/error-state";
import { StatusBadge } from "@/src/components/ui/status-badge";
import { useWorkspaceRole } from "@/src/features/identity/queries";
import {
  authorName,
  contentTitle,
  detailStatusLabel,
  formatMetric,
  inspirationStatusLabel,
} from "@/src/features/inspirations/presentation";
import {
  type InspirationAction,
  useArchiveInspiration,
  useInspiration,
  useInspirationAction,
  useInspirationEvidence,
  useCreateTopicFromInspiration,
  useUpdateInspiration,
} from "@/src/features/inspirations/queries";
import type { AnalysisRun } from "@/src/features/inspirations/types";
import { useCreatePatternsFromAnalysis } from "@/src/features/patterns/queries";
import { formatRelativeTime, platformLabel } from "@/src/lib/format";

export function InspirationDetailPage({
  workspaceId,
  inspirationId,
}: {
  workspaceId: string;
  inspirationId: string;
}) {
  const inspiration = useInspiration(workspaceId, inspirationId);
  const evidence = useInspirationEvidence(workspaceId, inspirationId);
  const permission = useWorkspaceRole(workspaceId);
  const update = useUpdateInspiration(workspaceId, inspirationId);
  const archive = useArchiveInspiration(workspaceId, inspirationId);
  const action = useInspirationAction(workspaceId, inspirationId);
  const topic = useCreateTopicFromInspiration(workspaceId, inspirationId);
  const [topicOpen, setTopicOpen] = useState(false);
  const l1 = latestRun(evidence.analyses.data, "l1");
  const l2 = latestRun(evidence.analyses.data, "l2");
  const patternSource = l2?.status === "succeeded" ? l2 : l1;
  const patterns = useCreatePatternsFromAnalysis(
    workspaceId,
    patternSource?.id,
  );

  if (inspiration.isLoading) {
    return (
      <div aria-label="正在加载灵感详情" className="animate-pulse space-y-5">
        <div className="h-5 w-28 rounded bg-surface-subtle" />
        <div className="h-52 rounded-2xl bg-surface" />
        <div className="grid gap-5 xl:grid-cols-2">
          <div className="h-80 rounded-xl bg-surface" />
          <div className="h-80 rounded-xl bg-surface" />
        </div>
      </div>
    );
  }

  if (inspiration.error || !inspiration.data) {
    return (
      <section className="rounded-xl border border-border bg-surface">
        <ErrorState
          message={
            (inspiration.error as { message?: string })?.message ??
            "没有找到这条灵感。"
          }
          onRetry={() => inspiration.refetch()}
          requestId={(inspiration.error as { requestId?: string })?.requestId}
        />
      </section>
    );
  }

  const item = inspiration.data;
  const latestScore = evidence.scores.data?.[0];
  const latestTranscript = evidence.transcripts.data?.[0];
  const anyEvidenceError = [
    evidence.scores.error,
    evidence.metrics.error,
    evidence.comments.error,
    evidence.analyses.error,
    evidence.transcripts.error,
  ].find(Boolean);
  const latestMetrics = evidence.metrics.data?.[0];

  function run(next: InspirationAction) {
    if (
      next !== "score" &&
      !window.confirm(
        "这会创建 1 个外部或 AI 任务，并受工作区预算限制。任务创建不代表处理完成，是否继续？",
      )
    ) {
      return;
    }
    action.mutate(next);
  }

  return (
    <>
      <Link
        className="mb-5 inline-flex items-center gap-2 text-xs font-medium text-text-muted hover:text-text"
        href={`/w/${workspaceId}/inspirations`}
      >
        <ArrowLeft aria-hidden="true" size={14} />
        返回灵感库
      </Link>

      <section className="mb-5 overflow-hidden rounded-2xl border border-border bg-surface shadow-panel">
        <div className="h-1.5 bg-gradient-to-r from-violet-600 via-primary-500 to-cyan-300" />
        <div className="grid gap-6 p-5 sm:p-7 xl:grid-cols-[1fr_auto]">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs font-semibold tracking-[0.12em] text-primary-600 uppercase">
                {platformLabel(item.content.platform)} · {item.content.content_type}
              </span>
              <StatusBadge
                label={inspirationStatusLabel(item.status)}
                status={item.status === "archived" ? "paused" : item.status}
              />
              <StatusBadge
                label={detailStatusLabel(item.content.detail_status)}
                status={
                  item.content.detail_status === "ready" ||
                  item.content.detail_status === "detail"
                    ? "succeeded"
                    : "pending"
                }
              />
            </div>
            <h1 className="mt-3 max-w-4xl text-2xl font-semibold leading-9 tracking-tight sm:text-3xl">
              {contentTitle(item.content.title, item.content.body_text)}
            </h1>
            <p className="mt-3 text-sm text-text-muted">
              {authorName(item.content.author_snapshot)} · 发布于{" "}
              {item.content.published_at
                ? new Date(item.content.published_at).toLocaleString("zh-CN")
                : "未知时间"}{" "}
              · 收录于 {formatRelativeTime(item.created_at)}
            </p>
          </div>
          <div className="flex flex-wrap items-start gap-2">
            <a
              className="inline-flex items-center gap-2 rounded-lg border border-border px-3.5 py-2.5 text-sm font-medium hover:bg-surface-subtle"
              href={item.content.canonical_url}
              rel="noreferrer"
              target="_blank"
            >
              <ExternalLink aria-hidden="true" size={15} />
              查看原内容
            </a>
            {permission.canEdit ? (
              <>
                <button
                  className="inline-flex items-center gap-2 rounded-lg border border-primary-200 bg-primary-50 px-3.5 py-2.5 text-sm font-medium text-primary-700 hover:bg-primary-100 disabled:opacity-50"
                  disabled={action.isPending}
                  onClick={() => run("hydrate-detail")}
                  type="button"
                >
                  <RefreshCw aria-hidden="true" size={15} />
                  {item.content.detail_status === "ready" ||
                  item.content.detail_status === "detail"
                    ? "刷新指标"
                    : "补全详情"}
                </button>
                <button
                  className="inline-flex items-center gap-2 rounded-lg bg-primary-600 px-3.5 py-2.5 text-sm font-medium text-white hover:bg-primary-700"
                  onClick={() => setTopicOpen(true)}
                  type="button"
                >
                  <Sparkles aria-hidden="true" size={15} />
                  转成选题
                </button>
                <button
                  className="inline-flex items-center gap-2 rounded-lg border border-border px-3.5 py-2.5 text-sm font-medium hover:bg-surface-subtle disabled:opacity-50"
                  disabled={archive.isPending}
                  onClick={() => archive.mutate(item.status !== "archived")}
                  type="button"
                >
                  {item.status === "archived" ? (
                    <RotateCcw aria-hidden="true" size={15} />
                  ) : (
                    <Archive aria-hidden="true" size={15} />
                  )}
                  {item.status === "archived" ? "恢复" : "归档"}
                </button>
              </>
            ) : null}
          </div>
        </div>
      </section>

      {action.isSuccess ? (
        <div className="mb-5 flex items-center justify-between gap-4 rounded-xl border border-blue-100 bg-primary-50 px-4 py-3 text-sm text-primary-700">
          <span>
            {action.data?.action === "hydrate-detail"
              ? "详情刷新任务已受理；任务完成后会写入最新正文、媒体和互动指标。"
              : "请求已受理。异步操作仍需等待任务完成，当前页面不会提前标记为已完成。"}
          </span>
          <Link className="shrink-0 font-semibold underline" href={`/w/${workspaceId}/jobs`}>
            查看任务
          </Link>
        </div>
      ) : null}
      {action.error ? (
        <div className="mb-5 rounded-xl border border-red-100 bg-red-50 px-4 py-3 text-sm text-red-700">
          {(action.error as { message?: string }).message ?? "操作失败，请重试。"}
        </div>
      ) : null}
      {anyEvidenceError ? (
        <div className="mb-5 rounded-xl border border-amber-100 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          部分证据读取失败；原内容仍可查看，分析结果没有被推测或补造。
        </div>
      ) : null}

      <div className="grid gap-5 xl:grid-cols-[1.25fr_0.75fr]">
        <div className="space-y-5">
          <section className="rounded-xl border border-border bg-surface p-5 shadow-panel sm:p-6">
            <SectionTitle
              icon={Sparkles}
              eyebrow="Source"
              title="原文与采集状态"
            />
            <p className="mt-5 whitespace-pre-line text-sm leading-7 text-text">
              {item.content.body_text || "当前内容源未提供可读取的正文。"}
            </p>
            <div className="mt-5 grid gap-3 border-t border-border pt-5 text-xs sm:grid-cols-3">
              <Fact label="详情状态" value={detailStatusLabel(item.content.detail_status)} />
              <Fact
                label="最新互动快照"
                value={
                  latestMetrics
                    ? `浏览 ${formatMetric(latestMetrics.views)} · 赞 ${formatMetric(latestMetrics.likes)} · 评 ${formatMetric(latestMetrics.comments)} · 藏 ${formatMetric(latestMetrics.favorites)}`
                    : "尚无快照"
                }
              />
              <Fact label="最后看见" value={formatRelativeTime(item.content.last_seen_at)} />
            </div>
          </section>

          <section className="rounded-xl border border-border bg-surface p-5 shadow-panel sm:p-6">
            <SectionTitle icon={Gauge} eyebrow="Snapshot" title="指标快照" />
            {evidence.metrics.isLoading ? (
              <div className="mt-5"><LoadingLine /></div>
            ) : evidence.metrics.data?.length ? (
              <div className="mt-5 overflow-x-auto">
                <table className="w-full min-w-[620px] text-left text-xs">
                  <thead className="text-text-muted">
                    <tr>
                      <th className="pb-3 font-medium">采集时间</th>
                      <th className="pb-3 text-right font-medium">播放</th>
                      <th className="pb-3 text-right font-medium">点赞</th>
                      <th className="pb-3 text-right font-medium">评论</th>
                      <th className="pb-3 text-right font-medium">收藏</th>
                      <th className="pb-3 text-right font-medium">分享</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {evidence.metrics.data.map((snapshot) => (
                      <tr key={snapshot.id}>
                        <td className="py-3">{new Date(snapshot.captured_at).toLocaleString("zh-CN")}</td>
                        {[snapshot.views, snapshot.likes, snapshot.comments, snapshot.favorites, snapshot.shares].map((value, index) => (
                          <td className="py-3 text-right tabular-nums" key={index}>
                            {formatMetric(value)}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="mt-5"><Absent text="还没有已入库的指标快照；缺失值不会显示为 0。" /></div>
            )}
          </section>

          <EvidenceSection
            actionLabel="运行 L1 分析"
            busy={action.isPending}
            canEdit={permission.canEdit}
            icon={Bot}
            onAction={() => run("analysis-l1")}
            title="结构化分析 · L1"
          >
            <AnalysisResult run={l1} />
          </EvidenceSection>

          <EvidenceSection
            actionLabel="运行 L2 深度分析"
            busy={action.isPending}
            canEdit={permission.canEdit}
            icon={Sparkles}
            onAction={() => run("analysis-l2")}
            title="深度分析 · L2"
          >
            <AnalysisResult run={l2} />
          </EvidenceSection>

          <section className="rounded-xl border border-border bg-surface p-5 shadow-panel sm:p-6">
            <div className="flex items-center justify-between gap-4">
              <SectionTitle icon={Tags} eyebrow="Pattern" title="提炼可复用模式" />
              {permission.canEdit ? (
                <button
                  className="rounded-lg border border-border px-3 py-2 text-xs font-medium disabled:opacity-50"
                  disabled={!patternSource || patterns.isPending}
                  onClick={() => patterns.mutate()}
                  type="button"
                >
                  从成功分析提炼
                </button>
              ) : null}
            </div>
            <p className="mt-4 text-sm leading-6 text-text-muted">
              系统只从成功的 L1/L2 结构化结果创建模式草稿，并保留分析与来源引用。
            </p>
            {patterns.isSuccess ? (
              <div className="mt-4 rounded-lg bg-emerald-50 p-3 text-sm text-emerald-800">
                已创建 {patterns.data.length} 个模式草稿。
                <Link className="ml-2 font-semibold underline" href={`/w/${workspaceId}/patterns`}>
                  前往查看
                </Link>
              </div>
            ) : patterns.error ? (
              <p className="mt-4 rounded-lg bg-red-50 p-3 text-xs text-red-700">
                {(patterns.error as { message?: string }).message ?? "模式提炼失败。"}
              </p>
            ) : null}
          </section>

          <EvidenceSection
            actionLabel="创建转写任务"
            busy={action.isPending}
            canEdit={permission.canEdit}
            icon={FileAudio}
            onAction={() => run("transcript")}
            title="内容转写"
          >
            {evidence.transcripts.isLoading ? (
              <LoadingLine />
            ) : latestTranscript ? (
              <div>
                <StatusBadge
                  label={latestTranscript.status}
                  status={latestTranscript.status}
                />
                <p className="mt-4 whitespace-pre-line text-sm leading-7">
                  {latestTranscript.text || "转写任务尚未产出文本。"}
                </p>
                <p className="mt-3 text-xs text-text-muted">
                  {latestTranscript.provider} · {latestTranscript.model} ·
                  置信度 {latestTranscript.confidence ?? "—"}
                </p>
              </div>
            ) : (
              <Absent text="还没有转写记录。" />
            )}
          </EvidenceSection>

          <EvidenceSection
            actionLabel="抓取最新评论"
            busy={action.isPending}
            canEdit={permission.canEdit}
            icon={MessageCircle}
            onAction={() => run("comments")}
            title="评论样本"
          >
            {evidence.comments.isLoading ? (
              <LoadingLine />
            ) : evidence.comments.data?.length ? (
              <div className="divide-y divide-border">
                {evidence.comments.data.slice(0, 8).map((comment) => (
                  <article className="py-4 first:pt-0 last:pb-0" key={comment.id}>
                    <div className="flex items-center justify-between gap-3 text-xs text-text-muted">
                      <span>{authorName(comment.author_snapshot)}</span>
                      <span>{comment.like_count == null ? "赞 —" : `${comment.like_count} 赞`}</span>
                    </div>
                    <p className="mt-2 text-sm leading-6">{comment.body_text}</p>
                  </article>
                ))}
              </div>
            ) : (
              <Absent text="还没有已入库的评论样本。" />
            )}
          </EvidenceSection>
        </div>

        <aside className="space-y-5">
          <EvidenceSection
            actionLabel="重新计算"
            busy={action.isPending}
            canEdit={permission.canEdit}
            icon={Gauge}
            onAction={() => run("score")}
            title="评分证据"
          >
            {evidence.scores.isLoading ? (
              <LoadingLine />
            ) : latestScore ? (
              <>
                <div className="grid grid-cols-3 gap-3">
                  <Score label="等级" value={latestScore.grade} />
                  <Score label="R 值" value={latestScore.r_value ?? "—"} />
                  <Score label="M 值" value={latestScore.m_value ?? "—"} />
                </div>
                <p className="mt-4 text-xs leading-5 text-text-muted">
                  核心指标 {latestScore.core_metric ?? "—"} · 基线{" "}
                  {latestScore.baseline_value ?? "—"} ·
                  {formatRelativeTime(latestScore.calculated_at)}
                </p>
                <div className="mt-3 rounded-lg bg-canvas/70 p-3 text-xs leading-5 text-text-muted">
                  {latestScore.is_initial
                    ? "首次评分证据已冻结，不会被后续重算覆盖。"
                    : "这是追加评分记录；历史首次证据仍保留。"}
                  {Array.isArray(latestScore.evidence.reasons) &&
                  latestScore.evidence.reasons.length
                    ? ` 证据状态：${latestScore.evidence.reasons.map(String).join("、")}。`
                    : ""}
                </div>
              </>
            ) : (
              <Absent text="还没有可用评分；不会用缺失指标推算等级。" />
            )}
          </EvidenceSection>

          <section className="rounded-xl border border-border bg-surface p-5 shadow-panel">
            <SectionTitle icon={Check} eyebrow="Curation" title="人工判断" />
            {permission.canEdit ? (
              <form
                className="mt-5 space-y-4"
                onSubmit={(event) => {
                  event.preventDefault();
                  const form = new FormData(event.currentTarget);
                  const notes = String(form.get("notes") ?? "").trim();
                  const score = String(form.get("manual_score") ?? "");
                  update.mutate({
                    notes: notes || null,
                    manual_score: score === "" ? null : Number(score),
                  });
                }}
              >
                <label className="block">
                  <span className="mb-2 block text-xs font-medium text-text-muted">
                    状态
                  </span>
                  <select
                    className="h-10 w-full rounded-lg border border-border bg-surface px-3 text-sm"
                    onChange={(event) =>
                      update.mutate({
                        status: event.target.value as
                          | "inbox"
                          | "analyzed"
                          | "candidate"
                          | "archived",
                      })
                    }
                    value={item.status}
                  >
                    <option value="inbox">待处理</option>
                    <option value="analyzed">已分析</option>
                    <option value="candidate">候选选题</option>
                    <option value="archived">已归档</option>
                  </select>
                </label>
                <label className="block">
                  <span className="mb-2 block text-xs font-medium text-text-muted">
                    人工评分（0–100）
                  </span>
                  <input
                    className="h-10 w-full rounded-lg border border-border px-3 text-sm"
                    max={100}
                    min={0}
                    defaultValue={item.manual_score ?? ""}
                    name="manual_score"
                    placeholder="未评分"
                    type="number"
                  />
                </label>
                <label className="block">
                  <span className="mb-2 block text-xs font-medium text-text-muted">
                    研究笔记
                  </span>
                  <textarea
                    className="min-h-28 w-full rounded-lg border border-border p-3 text-sm leading-6"
                    defaultValue={item.notes ?? ""}
                    name="notes"
                    placeholder="记录值得复用的钩子、结构与证据…"
                  />
                </label>
                <button
                  className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-primary-600 px-4 py-2.5 text-sm font-medium text-white disabled:opacity-60"
                  disabled={update.isPending}
                  type="submit"
                >
                  {update.isPending ? (
                    <LoaderCircle aria-hidden="true" className="animate-spin" size={15} />
                  ) : (
                    <Check aria-hidden="true" size={15} />
                  )}
                  保存人工判断
                </button>
              </form>
            ) : (
              <div className="mt-5 space-y-4">
                <Fact label="人工评分" value={item.manual_score == null ? "—" : String(item.manual_score)} />
                <Fact label="研究笔记" value={item.notes ?? "暂无笔记"} />
              </div>
            )}
          </section>
        </aside>
      </div>

      {topicOpen ? (
        <TopicDialog
          defaultTitle={contentTitle(item.content.title, item.content.body_text)}
          mutation={topic}
          onClose={() => setTopicOpen(false)}
        />
      ) : null}
    </>
  );
}

function TopicDialog({
  defaultTitle,
  mutation,
  onClose,
}: {
  defaultTitle: string;
  mutation: ReturnType<typeof useCreateTopicFromInspiration>;
  onClose: () => void;
}) {
  return (
    <div
      aria-modal="true"
      className="fixed inset-0 z-[70] grid place-items-center bg-text/30 p-4 backdrop-blur-sm"
      role="dialog"
    >
      <button aria-label="关闭" className="absolute inset-0" onClick={onClose} type="button" />
      <form
        className="relative w-full max-w-lg rounded-2xl border border-border bg-surface p-6 shadow-popover"
        onSubmit={(event) => {
          event.preventDefault();
          const data = new FormData(event.currentTarget);
          mutation.mutate({
            title: String(data.get("title") ?? ""),
            audience_problem: String(data.get("audience_problem") ?? "") || null,
            angle: String(data.get("angle") ?? "") || null,
            hook: String(data.get("hook") ?? "") || null,
          });
        }}
      >
        <p className="text-xs font-semibold tracking-[0.14em] text-primary-600 uppercase">
          Next workflow
        </p>
        <h2 className="mt-1 text-xl font-semibold">转成候选选题</h2>
        {mutation.data ? (
          <div className="mt-6 rounded-xl border border-emerald-100 bg-emerald-50 p-5">
            <p className="font-semibold text-emerald-800">选题已创建</p>
            <p className="mt-2 text-sm text-emerald-700">
              已保留灵感和内容证据引用。选题 ID：{mutation.data.id.slice(0, 8)}
            </p>
            <button
              className="mt-4 rounded-lg bg-emerald-700 px-4 py-2 text-sm font-medium text-white"
              onClick={onClose}
              type="button"
            >
              完成
            </button>
          </div>
        ) : (
          <>
            <div className="mt-6 space-y-4">
              {[
                { name: "title", label: "选题标题", value: defaultTitle, required: true },
                { name: "audience_problem", label: "受众问题", value: "" },
                { name: "angle", label: "内容角度", value: "" },
                { name: "hook", label: "开场钩子", value: "" },
              ].map((field) => (
                <label className="block" key={field.name}>
                  <span className="mb-2 block text-sm font-medium">{field.label}</span>
                  <input
                    className="h-10 w-full rounded-lg border border-border px-3 text-sm"
                    defaultValue={field.value}
                    name={field.name}
                    required={field.required}
                  />
                </label>
              ))}
            </div>
            {mutation.error ? (
              <p className="mt-4 rounded-lg bg-red-50 p-3 text-xs text-red-700">
                {(mutation.error as { message?: string }).message ?? "创建选题失败。"}
              </p>
            ) : null}
            <div className="mt-6 flex justify-end gap-2">
              <button className="rounded-lg border border-border px-4 py-2.5 text-sm" onClick={onClose} type="button">
                取消
              </button>
              <button
                className="rounded-lg bg-primary-600 px-4 py-2.5 text-sm font-medium text-white disabled:opacity-50"
                disabled={mutation.isPending}
                type="submit"
              >
                创建选题
              </button>
            </div>
          </>
        )}
      </form>
    </div>
  );
}

function EvidenceSection({
  icon,
  title,
  children,
  actionLabel,
  onAction,
  canEdit,
  busy,
}: {
  icon: typeof Sparkles;
  title: string;
  children: React.ReactNode;
  actionLabel: string;
  onAction: () => void;
  canEdit: boolean;
  busy: boolean;
}) {
  return (
    <section className="rounded-xl border border-border bg-surface p-5 shadow-panel sm:p-6">
      <div className="flex items-center justify-between gap-4">
        <SectionTitle icon={icon} eyebrow="Evidence" title={title} />
        {canEdit ? (
          <button
            className="shrink-0 rounded-lg border border-border px-3 py-2 text-xs font-medium hover:bg-surface-subtle disabled:opacity-50"
            disabled={busy}
            onClick={onAction}
            type="button"
          >
            {actionLabel}
          </button>
        ) : null}
      </div>
      <div className="mt-5">{children}</div>
    </section>
  );
}

function SectionTitle({
  icon: Icon,
  eyebrow,
  title,
}: {
  icon: typeof Sparkles;
  eyebrow: string;
  title: string;
}) {
  return (
    <div className="flex items-start gap-3">
      <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-primary-50 text-primary-600">
        <Icon aria-hidden="true" size={17} />
      </span>
      <div>
        <p className="text-[10px] font-semibold tracking-[0.14em] text-primary-600 uppercase">
          {eyebrow}
        </p>
        <h2 className="mt-0.5 font-semibold">{title}</h2>
      </div>
    </div>
  );
}

function AnalysisResult({ run }: { run?: AnalysisRun }) {
  if (!run) return <Absent text="还没有这一层级的分析记录。" />;
  return (
    <div>
      <div className="flex flex-wrap items-center gap-2">
        <StatusBadge label={run.status} status={run.status} />
        <span className="text-xs text-text-muted">
          {run.model_provider} · {run.model} · Prompt {run.prompt_version} ·{" "}
          {formatRelativeTime(run.created_at)}
        </span>
      </div>
      {run.result ? (
        <dl className="mt-4 grid gap-3">
          {Object.entries(run.result)
            .slice(0, 8)
            .map(([key, value]) => (
              <div className="rounded-lg bg-canvas/70 p-3" key={key}>
                <dt className="text-[11px] font-medium text-text-muted">{key}</dt>
                <dd className="mt-1 text-sm leading-6">{displayValue(value)}</dd>
              </div>
            ))}
        </dl>
      ) : (
        <p className="mt-4 text-sm text-text-muted">
          当前任务尚未产出结构化结果。
        </p>
      )}
      <div className="mt-4 grid gap-2 text-[11px] text-text-muted sm:grid-cols-3">
        <span>输入 Hash {run.input_hash.slice(0, 10)}</span>
        <span>
          Token {run.input_tokens ?? "—"} / {run.output_tokens ?? "—"}
        </span>
        <span>费用 US${Number(run.cost_usd).toFixed(4)}</span>
      </div>
      <div className="mt-3">
        <p className="text-[11px] font-medium text-text-muted">来源引用</p>
        {run.evidence_refs.length ? (
          <div className="mt-2 flex flex-wrap gap-2">
            {run.evidence_refs.slice(0, 8).map((ref, index) => (
              <span
                className="rounded-md bg-canvas px-2 py-1 font-mono text-[10px]"
                key={`${String(ref)}:${index}`}
              >
                {displayValue(ref)}
              </span>
            ))}
          </div>
        ) : (
          <p className="mt-1 text-xs text-text-muted">当前分析未返回来源引用。</p>
        )}
      </div>
    </div>
  );
}

function displayValue(value: unknown): string {
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  if (Array.isArray(value)) return value.map(displayValue).join(" · ");
  if (value && typeof value === "object") {
    return Object.entries(value)
      .slice(0, 5)
      .map(([key, nested]) => `${key}: ${displayValue(nested)}`)
      .join("；");
  }
  return "—";
}

function latestRun(runs: AnalysisRun[] | undefined, level: string) {
  return runs?.find((run) => run.analysis_level === level);
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-[11px] text-text-muted">{label}</p>
      <p className="mt-1 break-words text-sm font-medium">{value}</p>
    </div>
  );
}

function Score({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-canvas/70 p-3 text-center">
      <p className="text-[10px] text-text-muted">{label}</p>
      <strong className="mt-1 block text-xl font-semibold tabular-nums">{value}</strong>
    </div>
  );
}

function LoadingLine() {
  return <div className="h-16 animate-pulse rounded-lg bg-surface-subtle" />;
}

function Absent({ text }: { text: string }) {
  return (
    <div className="rounded-lg border border-dashed border-border bg-canvas/50 px-4 py-5 text-sm text-text-muted">
      {text}
    </div>
  );
}
