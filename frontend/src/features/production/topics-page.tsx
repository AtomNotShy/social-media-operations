"use client";

import { Archive, ArrowRight, CheckCircle2, Lightbulb, Plus, XCircle } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useMemo, useState } from "react";
import { EmptyState } from "@/src/components/ui/empty-state";
import { ErrorState } from "@/src/components/ui/error-state";
import { PageHeader } from "@/src/components/ui/page-header";
import { StatusBadge } from "@/src/components/ui/status-badge";
import { useWorkspaceRole } from "@/src/features/identity/queries";
import {
  useBulkUpdateTopics,
  useChannels,
  useCreateTopic,
  useTopics,
} from "@/src/features/production/queries";
import type { TopicCreate } from "@/src/features/production/types";
import {
  Dialog,
  InlineError,
  SavedViewPicker,
  inputClass,
  primaryButton,
  secondaryButton,
  textareaClass,
} from "@/src/features/production/ui";

const filters = [
  ["全部", ""],
  ["待评估", "idea"],
  ["已选中", "selected"],
  ["已拒绝", "rejected"],
  ["已归档", "archived"],
];

export function TopicsPage({ workspaceId }: { workspaceId: string }) {
  const router = useRouter();
  const params = useSearchParams();
  const status = params.get("status") || undefined;
  const query = params.get("q")?.trim().toLowerCase() ?? "";
  const topics = useTopics(workspaceId, status);
  const permission = useWorkspaceRole(workspaceId);
  const bulk = useBulkUpdateTopics(workspaceId);
  const [selected, setSelected] = useState<string[]>([]);
  const [createOpen, setCreateOpen] = useState(params.get("create") === "1");
  const visible = useMemo(
    () =>
      topics.data?.filter((item) =>
        [item.title, item.angle, item.hook, item.audience_problem].some((value) =>
          value?.toLowerCase().includes(query),
        ),
      ) ?? [],
    [query, topics.data],
  );

  function setParam(name: string, value: string) {
    const next = new URLSearchParams(params);
    if (value) next.set(name, value);
    else next.delete(name);
    router.replace(`?${next.toString()}`);
    setSelected([]);
  }

  const selectedTopics = visible.filter((item) => selected.includes(item.id));

  return (
    <>
      <PageHeader
        eyebrow="内容生产"
        title="候选选题"
        description="用受众问题、切入角度、开场钩子与证据来源判断是否值得进入生产。"
        actions={
          <div className="flex gap-2">
            <SavedViewPicker entityType="topics" workspaceId={workspaceId} />
            {permission.canEdit ? (
              <button className={primaryButton} onClick={() => setCreateOpen(true)} type="button">
                <Plus size={16} /> 新建选题
              </button>
            ) : null}
          </div>
        }
      />
      <div className="mb-4 flex flex-col gap-3 rounded-xl border border-border bg-surface p-3 sm:flex-row">
        <input
          className={`${inputClass} flex-1`}
          defaultValue={params.get("q") ?? ""}
          onKeyDown={(event) => {
            if (event.key === "Enter") setParam("q", event.currentTarget.value.trim());
          }}
          placeholder="搜索标题、角度、钩子（Enter）"
        />
        <div className="flex flex-wrap gap-2">
          {filters.map(([label, value]) => (
            <button
              className={`rounded-full border px-3 py-2 text-xs font-medium ${
                (status ?? "") === value
                  ? "border-text bg-text text-white"
                  : "border-border bg-surface"
              }`}
              key={value}
              onClick={() => setParam("status", value)}
              type="button"
            >
              {label}
            </button>
          ))}
        </div>
      </div>
      {selected.length ? (
        <div className="sticky top-14 z-10 mb-4 flex flex-wrap items-center gap-2 rounded-xl border border-primary-100 bg-primary-50 p-3 shadow-panel">
          <strong className="mr-auto text-sm">已选择 {selected.length} 个选题</strong>
          {[
            ["进入生产", "selected", CheckCircle2],
            ["拒绝", "rejected", XCircle],
            ["归档", "archived", Archive],
          ].map(([label, nextStatus, Icon]) => (
            <button
              className={secondaryButton}
              disabled={bulk.isPending}
              key={String(nextStatus)}
              onClick={() =>
                bulk.mutate(
                  {
                    topics: selectedTopics,
                    status: nextStatus as "selected" | "rejected" | "archived",
                  },
                  { onSuccess: () => setSelected([]) },
                )
              }
              type="button"
            >
              <Icon size={14} /> {label as string}
            </button>
          ))}
        </div>
      ) : null}
      {topics.isLoading ? (
        <div className="grid gap-4 lg:grid-cols-2">
          {Array.from({ length: 4 }).map((_, index) => (
            <div className="h-64 animate-pulse rounded-xl bg-surface" key={index} />
          ))}
        </div>
      ) : topics.error ? (
        <ErrorState message="选题列表加载失败。" onRetry={() => topics.refetch()} />
      ) : visible.length ? (
        <div className="grid gap-4 lg:grid-cols-2">
          {visible.map((topic) => (
            <article className="rounded-xl border border-border bg-surface p-5 shadow-panel" key={topic.id}>
              <div className="flex items-start gap-3">
                {permission.canEdit ? (
                  <input
                    aria-label={`选择${topic.title}`}
                    checked={selected.includes(topic.id)}
                    className="mt-1 size-4"
                    onChange={(event) =>
                      setSelected((items) =>
                        event.target.checked
                          ? [...items, topic.id]
                          : items.filter((id) => id !== topic.id),
                      )
                    }
                    type="checkbox"
                  />
                ) : null}
                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between gap-3">
                    <span className="grid size-9 place-items-center rounded-lg bg-primary-50 text-primary-600">
                      <Lightbulb size={17} />
                    </span>
                    <StatusBadge label={topicStatus(topic.status)} status={topic.status} />
                  </div>
                  <h2 className="mt-4 text-base font-semibold">{topic.title}</h2>
                  <dl className="mt-4 grid gap-3 text-sm">
                    <div>
                      <dt className="text-[11px] font-semibold text-text-muted uppercase">用户问题</dt>
                      <dd className="mt-1 leading-6">{topic.audience_problem || "尚未补充"}</dd>
                    </div>
                    <div>
                      <dt className="text-[11px] font-semibold text-text-muted uppercase">切入角度</dt>
                      <dd className="mt-1 leading-6">{topic.angle || "尚未补充"}</dd>
                    </div>
                    <div className="rounded-lg bg-surface-subtle p-3">
                      <dt className="text-[11px] font-semibold text-primary-600 uppercase">开场钩子</dt>
                      <dd className="mt-1 leading-6">{topic.hook || "尚未补充"}</dd>
                    </div>
                  </dl>
                  <Link
                    className="mt-4 inline-flex items-center gap-2 text-sm font-medium text-primary-600"
                    href={`/w/${workspaceId}/topics/${topic.id}`}
                  >
                    打开选题 <ArrowRight size={15} />
                  </Link>
                </div>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <section className="rounded-xl border border-border bg-surface">
          <EmptyState description="调整筛选，或从灵感详情转成候选选题。" title="没有符合条件的选题" />
        </section>
      )}
      <CreateTopicDialog
        onClose={() => setCreateOpen(false)}
        open={createOpen && permission.canEdit}
        workspaceId={workspaceId}
      />
    </>
  );
}

function CreateTopicDialog({
  workspaceId,
  open,
  onClose,
}: {
  workspaceId: string;
  open: boolean;
  onClose: () => void;
}) {
  const channels = useChannels(workspaceId);
  const create = useCreateTopic(workspaceId);
  const [value, setValue] = useState<TopicCreate>({
    title: "",
    status: "idea",
    evidence_refs: [],
  });
  return (
    <Dialog onClose={onClose} open={open} title="新建候选选题">
      <form
        className="grid gap-4"
        onSubmit={(event) => {
          event.preventDefault();
          create.mutate(value, { onSuccess: onClose });
        }}
      >
        <label className="text-sm font-medium">
          目标账号
          <select
            className={`${inputClass} mt-2`}
            onChange={(event) =>
              setValue({ ...value, owned_channel_id: event.target.value || null })
            }
            value={value.owned_channel_id ?? ""}
          >
            <option value="">稍后选择</option>
            {channels.data?.map((channel) => (
              <option key={channel.id} value={channel.id}>
                {channel.display_name}
              </option>
            ))}
          </select>
        </label>
        <Field label="标题" required value={value.title} onChange={(title) => setValue({ ...value, title })} />
        <Area label="用户问题" value={value.audience_problem ?? ""} onChange={(audience_problem) => setValue({ ...value, audience_problem })} />
        <Area label="切入角度" value={value.angle ?? ""} onChange={(angle) => setValue({ ...value, angle })} />
        <Area label="开场钩子" value={value.hook ?? ""} onChange={(hook) => setValue({ ...value, hook })} />
        <InlineError error={create.error} />
        <button className={primaryButton} disabled={create.isPending} type="submit">创建选题</button>
      </form>
    </Dialog>
  );
}

function Field({ label, value, onChange, required }: { label: string; value: string; onChange: (value: string) => void; required?: boolean }) {
  return <label className="text-sm font-medium">{label}<input className={`${inputClass} mt-2`} onChange={(event) => onChange(event.target.value)} required={required} value={value} /></label>;
}
function Area({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return <label className="text-sm font-medium">{label}<textarea className={`${textareaClass} mt-2 min-h-20`} onChange={(event) => onChange(event.target.value)} value={value} /></label>;
}
export function topicStatus(status: string) {
  return ({ idea: "待评估", selected: "已选中", rejected: "已拒绝", archived: "已归档" }[status] ?? status);
}
