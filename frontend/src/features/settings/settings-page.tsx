"use client";

import {
  Activity,
  BellRing,
  CheckCircle2,
  CirclePause,
  Database,
  LoaderCircle,
  LockKeyhole,
  Play,
  Save,
  ShieldAlert,
  ShieldCheck,
  Trash2,
  UserPlus,
  Users,
} from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { ErrorState } from "@/src/components/ui/error-state";
import { PageHeader } from "@/src/components/ui/page-header";
import { AutomationSettingsPanel } from "@/src/features/automation/automation-settings-panel";
import { useWorkspaceRole } from "@/src/features/identity/queries";
import {
  InlineError,
  inputClass,
  primaryButton,
  secondaryButton,
} from "@/src/features/production/ui";
import { AISettingsPanel } from "@/src/features/settings/ai-settings-panel";
import {
  useAddMember,
  useExternalCallsAction,
  useMembers,
  useProviderHealth,
  useQueueHealth,
  useRemoveMember,
  useUpdateMember,
  useUpdateWorkspace,
  useWorkspaceSettings,
} from "@/src/features/settings/queries";
import {
  externalCallsState,
  type Workspace,
  type WorkspaceMemberAdd,
} from "@/src/features/settings/types";

const roleLabels = {
  owner: "Owner",
  editor: "Editor",
  viewer: "Viewer",
} as const;

type WorkspaceForm = {
  name: string;
  timezone: string;
  providerBudget: string;
  aiBudget: string;
};

export function SettingsPage({ workspaceId }: { workspaceId: string }) {
  const permission = useWorkspaceRole(workspaceId);
  const workspace = useWorkspaceSettings(workspaceId);
  const members = useMembers(workspaceId, permission.isOwner);
  const provider = useProviderHealth(workspaceId);
  const queue = useQueueHealth(workspaceId);
  const callsAction = useExternalCallsAction(workspaceId);
  const calls = externalCallsState(workspace.data);

  return (
    <>
      <PageHeader
        eyebrow="系统"
        title="工作区设置"
        description="管理工作区信息、调用预算、运行安全与成员权限。供应商密钥由服务端安全托管，不会进入浏览器。"
      />

      <section className="mb-5 grid gap-3 md:grid-cols-3">
        <StatusCard
          detail={
            provider.data?.endpoints.length
              ? `近 24 小时 ${provider.data.endpoints.reduce((sum, item) => sum + item.request_count_24h, 0)} 次调用`
              : "暂无近 24 小时调用"
          }
          icon={Database}
          label="数据连接"
          status={providerStatus(provider.data?.endpoints)}
          tone={
            provider.data?.endpoints.some(
              (item) => item.circuit.state !== "closed",
            )
              ? "warning"
              : "success"
          }
        />
        <StatusCard
          detail={
            queue.data
              ? `${queue.data.active_count} 个活跃任务，${queue.data.stale_running_count} 个停滞`
              : "正在读取队列"
          }
          icon={Activity}
          label="任务队列"
          status={
            queue.data?.stale_running_count
              ? "需要处理"
              : queue.data
                ? "运行正常"
                : "读取中"
          }
          tone={queue.data?.stale_running_count ? "warning" : "success"}
        />
        <StatusCard
          detail="失败任务与人工处理项进入任务中心；邮件、Slack 尚未连接"
          icon={BellRing}
          label="任务通知"
          status="站内已接入"
          tone="neutral"
        />
      </section>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.3fr)_minmax(320px,0.7fr)]">
        <div className="space-y-5">
          <Panel
            description={
              permission.isOwner
                ? "修改名称、时区及每日费用上限。"
                : "当前角色可查看设置，只有 Owner 可以修改。"
            }
            icon={LockKeyhole}
            title="基本信息与预算"
          >
            {workspace.isLoading ? (
              <LoadingRows />
            ) : workspace.error ? (
              <ErrorState
                message={
                  (workspace.error as { message?: string }).message ??
                  "工作区设置暂时无法读取。"
                }
                onRetry={() => workspace.refetch()}
                requestId={
                  (workspace.error as { requestId?: string }).requestId
                }
              />
            ) : workspace.data ? (
              <WorkspaceSettingsForm
                canManage={permission.isOwner}
                key={workspace.data.updated_at}
                workspace={workspace.data}
                workspaceId={workspaceId}
              />
            ) : (
              <LoadingRows />
            )}
          </Panel>

          <AISettingsPanel
            canManage={permission.isOwner}
            workspaceId={workspaceId}
          />

          <AutomationSettingsPanel
            canManage={permission.isOwner}
            workspaceId={workspaceId}
          />

          <MembersPanel
            canManage={permission.isOwner}
            error={members.error}
            isLoading={members.isLoading}
            members={members.data ?? []}
            onRetry={() => members.refetch()}
            workspaceId={workspaceId}
          />
        </div>

        <div className="space-y-5">
          <ExternalCallsPanel
            canManage={permission.isOwner}
            changedAt={calls.changedAt}
            error={callsAction.error}
            isPending={callsAction.isPending}
            onPause={(reason) =>
              callsAction.mutate({ action: "pause", reason })
            }
            onResume={() => callsAction.mutate({ action: "resume" })}
            paused={calls.paused}
            reason={calls.reason}
          />

          <Panel
            description="运行数据每 30–60 秒自动刷新。"
            icon={Activity}
            title="系统健康"
          >
            <div className="space-y-3">
              <HealthRow
                detail={providerHealthDetail(provider.data?.endpoints)}
                label="TikHub 数据服务"
                status={providerStatus(provider.data?.endpoints)}
              />
              <HealthRow
                detail={
                  queue.data
                    ? `${queue.data.active_count} 个活跃任务`
                    : "等待服务端响应"
                }
                label="后台任务队列"
                status={
                  queue.data?.stale_running_count
                    ? `${queue.data.stale_running_count} 个停滞`
                    : queue.data
                      ? "正常"
                      : "读取中"
                }
                warning={Boolean(queue.data?.stale_running_count)}
              />
            </div>
            {provider.error || queue.error ? (
              <p className="mt-4 rounded-lg bg-warning/10 p-3 text-xs leading-5 text-text-muted">
                健康状态暂时无法完整读取，不影响浏览已保存内容。
              </p>
            ) : null}
            <div className="mt-4 flex flex-wrap gap-2">
              <Link
                className={secondaryButton}
                href={`/w/${workspaceId}/jobs`}
              >
                查看任务中心
              </Link>
              <Link
                className={secondaryButton}
                href={`/w/${workspaceId}/usage`}
              >
                查看用量费用
              </Link>
            </div>
          </Panel>

          <Panel
            description="浏览器只显示连接状态和运行结果。"
            icon={ShieldCheck}
            title="凭据与通知边界"
          >
            <ul className="space-y-3 text-sm leading-6">
              <BoundaryItem
                detail="可由 Owner 在当前控制台写入或更新；服务端加密保存，页面只返回末四位掩码。"
                label="AI Provider 凭据"
                status="可配置"
              />
              <BoundaryItem
                detail="TikHub 密钥由后端运行环境托管，页面不会返回或缓存明文。"
                label="TikHub 凭据"
                status="后端托管"
              />
              <BoundaryItem
                detail="同步失败、重试和人工处理项会进入任务中心。"
                label="站内任务提醒"
                status="已接入"
              />
              <BoundaryItem
                detail="当前后端没有邮件、Slack 或企业微信通知配置接口。"
                label="外部通知"
                status="未连接"
              />
            </ul>
          </Panel>
        </div>
      </div>
    </>
  );
}

function WorkspaceSettingsForm({
  workspaceId,
  workspace,
  canManage,
}: {
  workspaceId: string;
  workspace: Workspace;
  canManage: boolean;
}) {
  const updateWorkspace = useUpdateWorkspace(workspaceId);
  const [form, setForm] = useState<WorkspaceForm>({
    name: workspace.name,
    timezone: workspace.timezone,
    providerBudget: workspace.daily_provider_budget_usd,
    aiBudget: workspace.daily_ai_budget_usd,
  });
  const [saved, setSaved] = useState(false);

  return (
    <form
      className="grid gap-4"
      onSubmit={(event) => {
        event.preventDefault();
        setSaved(false);
        updateWorkspace.mutate(
          {
            name: form.name.trim(),
            timezone: form.timezone,
            daily_provider_budget_usd: form.providerBudget,
            daily_ai_budget_usd: form.aiBudget,
          },
          { onSuccess: () => setSaved(true) },
        );
      }}
    >
      <div className="grid gap-4 md:grid-cols-2">
        <Field label="工作区名称">
          <input
            className={inputClass}
            disabled={!canManage}
            maxLength={255}
            onChange={(event) =>
              setForm({ ...form, name: event.target.value })
            }
            required
            value={form.name}
          />
        </Field>
        <Field label="时区">
          <select
            className={inputClass}
            disabled={!canManage}
            onChange={(event) =>
              setForm({ ...form, timezone: event.target.value })
            }
            value={form.timezone}
          >
            <option value="Australia/Melbourne">Australia/Melbourne</option>
            <option value="Asia/Shanghai">Asia/Shanghai</option>
            <option value="UTC">UTC</option>
          </select>
        </Field>
        <Field
          helper="限制外部数据供应商的每日预计支出"
          label="数据日预算（USD）"
        >
          <input
            className={inputClass}
            disabled={!canManage}
            min="0"
            onChange={(event) =>
              setForm({ ...form, providerBudget: event.target.value })
            }
            step="0.5"
            type="number"
            value={form.providerBudget}
          />
        </Field>
        <Field
          helper="限制生成与分析模型的每日预计支出"
          label="AI 日预算（USD）"
        >
          <input
            className={inputClass}
            disabled={!canManage}
            min="0"
            onChange={(event) =>
              setForm({ ...form, aiBudget: event.target.value })
            }
            step="0.5"
            type="number"
            value={form.aiBudget}
          />
        </Field>
      </div>
      <InlineError error={updateWorkspace.error} />
      {canManage ? (
        <div className="flex items-center gap-3">
          <button
            className={primaryButton}
            disabled={updateWorkspace.isPending || !form.name.trim()}
            type="submit"
          >
            {updateWorkspace.isPending ? (
              <LoaderCircle className="animate-spin" size={15} />
            ) : (
              <Save size={15} />
            )}
            保存设置
          </button>
          {saved ? (
            <span className="inline-flex items-center gap-1.5 text-xs text-success">
              <CheckCircle2 size={14} />
              已保存
            </span>
          ) : null}
        </div>
      ) : null}
    </form>
  );
}

function Panel({
  title,
  description,
  icon: Icon,
  children,
}: {
  title: string;
  description: string;
  icon: typeof Activity;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-xl border border-border bg-surface shadow-panel">
      <div className="flex items-start gap-3 border-b border-border p-5">
        <span className="rounded-lg bg-primary-50 p-2 text-primary-600">
          <Icon aria-hidden="true" size={18} />
        </span>
        <div>
          <h2 className="font-semibold">{title}</h2>
          <p className="mt-1 text-xs leading-5 text-text-muted">
            {description}
          </p>
        </div>
      </div>
      <div className="p-5">{children}</div>
    </section>
  );
}

function StatusCard({
  icon: Icon,
  label,
  status,
  detail,
  tone,
}: {
  icon: typeof Activity;
  label: string;
  status: string;
  detail: string;
  tone: "success" | "warning" | "neutral";
}) {
  const toneClass =
    tone === "warning"
      ? "bg-warning/10 text-warning"
      : tone === "success"
        ? "bg-success/10 text-success"
        : "bg-primary-50 text-primary-600";
  return (
    <article className="rounded-xl border border-border bg-surface p-4 shadow-panel">
      <div className="flex items-start justify-between gap-3">
        <span className={`rounded-lg p-2 ${toneClass}`}>
          <Icon aria-hidden="true" size={18} />
        </span>
        <span className={`rounded-full px-2.5 py-1 text-[11px] font-medium ${toneClass}`}>
          {status}
        </span>
      </div>
      <h2 className="mt-4 text-sm font-semibold">{label}</h2>
      <p className="mt-1 text-xs leading-5 text-text-muted">{detail}</p>
    </article>
  );
}

function Field({
  label,
  helper,
  children,
}: {
  label: string;
  helper?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block text-sm font-medium">
      <span className="mb-2 block">{label}</span>
      {children}
      {helper ? (
        <span className="mt-1.5 block text-[11px] font-normal text-text-muted">
          {helper}
        </span>
      ) : null}
    </label>
  );
}

function MembersPanel({
  workspaceId,
  canManage,
  members,
  isLoading,
  error,
  onRetry,
}: {
  workspaceId: string;
  canManage: boolean;
  members: ReturnType<typeof useMembers>["data"] extends infer T
    ? NonNullable<T>
    : never;
  isLoading: boolean;
  error: unknown;
  onRetry: () => void;
}) {
  const addMember = useAddMember(workspaceId);
  const updateMember = useUpdateMember(workspaceId);
  const removeMember = useRemoveMember(workspaceId);
  const [userId, setUserId] = useState("");
  const [role, setRole] = useState<WorkspaceMemberAdd["role"]>("editor");

  return (
    <Panel
      description={
        canManage
          ? "添加已登录过系统的用户，并控制工作区级角色。"
          : "成员名单仅对 Owner 开放；你的当前权限为只读。"
      }
      icon={Users}
      title="成员与权限"
    >
      {!canManage ? (
        <div className="flex items-start gap-3 rounded-lg bg-surface-subtle p-4 text-sm leading-6 text-text-muted">
          <ShieldCheck className="mt-0.5 shrink-0" size={18} />
          只有 Owner 可以查看成员名单、调整角色或移除成员。
        </div>
      ) : isLoading ? (
        <LoadingRows />
      ) : error ? (
        <ErrorState
          message={
            (error as { message?: string }).message ?? "成员名单暂时无法读取。"
          }
          onRetry={onRetry}
          requestId={(error as { requestId?: string }).requestId}
        />
      ) : (
        <>
          <div className="divide-y divide-border">
            {members.map((member) => (
              <div
                className="flex flex-col gap-3 py-4 first:pt-0 sm:flex-row sm:items-center"
                key={member.id}
              >
                <span className="grid size-9 shrink-0 place-items-center rounded-full bg-primary-50 text-sm font-semibold text-primary-700">
                  {member.user.display_name.slice(0, 1).toUpperCase()}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium">
                    {member.user.display_name}
                  </p>
                  <p className="truncate text-xs text-text-muted">
                    {member.user.email ?? member.user.id}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <select
                    aria-label={`调整 ${member.user.display_name} 的角色`}
                    className="h-9 rounded-lg border border-border bg-surface px-2 text-xs"
                    disabled={updateMember.isPending}
                    onChange={(event) =>
                      updateMember.mutate({
                        userId: member.user.id,
                        input: {
                          role: event.target
                            .value as WorkspaceMemberAdd["role"],
                        },
                      })
                    }
                    value={member.role}
                  >
                    {Object.entries(roleLabels).map(([value, label]) => (
                      <option key={value} value={value}>
                        {label}
                      </option>
                    ))}
                  </select>
                  <button
                    aria-label={`移除 ${member.user.display_name}`}
                    className="grid size-9 place-items-center rounded-lg border border-border text-text-muted hover:border-danger hover:text-danger disabled:opacity-50"
                    disabled={removeMember.isPending}
                    onClick={() => removeMember.mutate(member.user.id)}
                    type="button"
                  >
                    <Trash2 size={15} />
                  </button>
                </div>
              </div>
            ))}
          </div>
          <form
            className="mt-4 grid gap-3 rounded-lg bg-surface-subtle p-4 sm:grid-cols-[1fr_110px_auto]"
            onSubmit={(event) => {
              event.preventDefault();
              addMember.mutate(
                { user_id: userId.trim(), role },
                { onSuccess: () => setUserId("") },
              );
            }}
          >
            <label className="text-xs font-medium">
              用户 ID
              <input
                className={`${inputClass} mt-1 min-h-10`}
                onChange={(event) => setUserId(event.target.value)}
                placeholder="用户登录后生成的 UUID"
                required
                value={userId}
              />
            </label>
            <label className="text-xs font-medium">
              角色
              <select
                className={`${inputClass} mt-1 min-h-10`}
                onChange={(event) =>
                  setRole(event.target.value as WorkspaceMemberAdd["role"])
                }
                value={role}
              >
                {Object.entries(roleLabels).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
            <button
              className={`${primaryButton} self-end`}
              disabled={!userId.trim() || addMember.isPending}
              type="submit"
            >
              {addMember.isPending ? (
                <LoaderCircle className="animate-spin" size={15} />
              ) : (
                <UserPlus size={15} />
              )}
              添加
            </button>
          </form>
          <InlineError
            error={
              addMember.error ?? updateMember.error ?? removeMember.error
            }
          />
          <p className="mt-3 text-[11px] leading-5 text-text-muted">
            用户必须至少登录过一次才能被添加；系统会阻止移除或降级最后一位 Owner。
          </p>
        </>
      )}
    </Panel>
  );
}

function ExternalCallsPanel({
  paused,
  reason,
  changedAt,
  canManage,
  isPending,
  error,
  onPause,
  onResume,
}: {
  paused: boolean;
  reason: string | null;
  changedAt: string | null;
  canManage: boolean;
  isPending: boolean;
  error: unknown;
  onPause: (reason: string) => void;
  onResume: () => void;
}) {
  const [pauseReason, setPauseReason] = useState("");
  return (
    <Panel
      description="用于供应商异常、费用失控或凭据风险时立即停止新外部调用。"
      icon={paused ? ShieldAlert : ShieldCheck}
      title="外部调用安全开关"
    >
      <div
        className={`rounded-lg border p-4 ${
          paused
            ? "border-danger/20 bg-danger/5"
            : "border-success/20 bg-success/5"
        }`}
      >
        <div className="flex items-center gap-2">
          {paused ? (
            <CirclePause className="text-danger" size={18} />
          ) : (
            <CheckCircle2 className="text-success" size={18} />
          )}
          <strong className="text-sm">
            {paused ? "外部调用已暂停" : "外部调用正常"}
          </strong>
        </div>
        <p className="mt-2 text-xs leading-5 text-text-muted">
          {paused
            ? reason || "Owner 已暂停新供应商和 AI 调用。"
            : "扫描、详情同步和生成任务可以按预算继续发起外部请求。"}
        </p>
        {changedAt ? (
          <p className="mt-1 text-[11px] text-text-muted">
            最近变更：{formatDateTime(changedAt)}
          </p>
        ) : null}
      </div>
      {canManage ? (
        paused ? (
          <button
            className={`${primaryButton} mt-4 w-full`}
            disabled={isPending}
            onClick={onResume}
            type="button"
          >
            {isPending ? (
              <LoaderCircle className="animate-spin" size={15} />
            ) : (
              <Play size={15} />
            )}
            恢复外部调用
          </button>
        ) : (
          <div className="mt-4">
            <label className="text-xs font-medium">
              暂停原因
              <input
                className={`${inputClass} mt-1`}
                onChange={(event) => setPauseReason(event.target.value)}
                placeholder="例如：供应商异常，等待排查"
                value={pauseReason}
              />
            </label>
            <button
              className="mt-3 inline-flex min-h-10 w-full items-center justify-center gap-2 rounded-lg border border-danger/30 bg-danger/5 px-4 py-2 text-sm font-medium text-danger hover:bg-danger/10 disabled:opacity-50"
              disabled={isPending || !pauseReason.trim()}
              onClick={() => onPause(pauseReason.trim())}
              type="button"
            >
              {isPending ? (
                <LoaderCircle className="animate-spin" size={15} />
              ) : (
                <CirclePause size={15} />
              )}
              暂停全部外部调用
            </button>
          </div>
        )
      ) : (
        <p className="mt-4 text-xs leading-5 text-text-muted">
          只有 Owner 可以更改此开关。
        </p>
      )}
      <InlineError error={error} />
    </Panel>
  );
}

function HealthRow({
  label,
  status,
  detail,
  warning = false,
}: {
  label: string;
  status: string;
  detail: string;
  warning?: boolean;
}) {
  return (
    <div className="flex items-start justify-between gap-4 rounded-lg bg-surface-subtle p-3">
      <div>
        <p className="text-xs font-semibold">{label}</p>
        <p className="mt-1 text-[11px] leading-5 text-text-muted">{detail}</p>
      </div>
      <span
        className={`shrink-0 rounded-full px-2 py-1 text-[10px] font-medium ${
          warning
            ? "bg-warning/10 text-warning"
            : "bg-success/10 text-success"
        }`}
      >
        {status}
      </span>
    </div>
  );
}

function BoundaryItem({
  label,
  detail,
  status,
}: {
  label: string;
  detail: string;
  status: string;
}) {
  return (
    <li className="flex items-start justify-between gap-3">
      <div>
        <p className="text-xs font-semibold">{label}</p>
        <p className="mt-1 text-[11px] leading-5 text-text-muted">{detail}</p>
      </div>
      <span className="shrink-0 rounded-full bg-surface-subtle px-2 py-1 text-[10px] font-medium text-text-muted">
        {status}
      </span>
    </li>
  );
}

function LoadingRows() {
  return (
    <div className="space-y-3" aria-label="正在加载">
      <div className="h-11 animate-pulse rounded-lg bg-surface-subtle" />
      <div className="h-11 animate-pulse rounded-lg bg-surface-subtle" />
    </div>
  );
}

function providerStatus(
  endpoints:
    | Array<{ circuit: { state: string } }>
    | undefined,
): string {
  if (!endpoints) return "读取中";
  if (endpoints.some((item) => item.circuit.state !== "closed")) {
    return "部分异常";
  }
  return endpoints.length ? "运行正常" : "等待调用";
}

function providerHealthDetail(
  endpoints:
    | Array<{
        request_count_24h: number;
        success_count_24h: number;
        average_latency_ms_24h: number | null;
      }>
    | undefined,
): string {
  if (!endpoints) return "等待服务端响应";
  const requests = endpoints.reduce(
    (sum, item) => sum + item.request_count_24h,
    0,
  );
  const successes = endpoints.reduce(
    (sum, item) => sum + item.success_count_24h,
    0,
  );
  if (!requests) return "近 24 小时没有新调用";
  const latency = endpoints
    .map((item) => item.average_latency_ms_24h)
    .filter((value): value is number => value !== null);
  const average = latency.length
    ? Math.round(latency.reduce((sum, value) => sum + value, 0) / latency.length)
    : null;
  return `近 24 小时成功率 ${((successes / requests) * 100).toFixed(1)}%${average === null ? "" : `，平均 ${average}ms`}`;
}

function formatDateTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("zh-CN", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}
