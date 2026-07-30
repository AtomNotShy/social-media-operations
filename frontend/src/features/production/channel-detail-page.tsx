"use client";

import { ArrowLeft, Save, ShieldAlert } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { ErrorState } from "@/src/components/ui/error-state";
import { PageHeader } from "@/src/components/ui/page-header";
import { useWorkspaceRole } from "@/src/features/identity/queries";
import {
  useChannel,
  useSavePositioning,
} from "@/src/features/production/queries";
import type { PositioningUpdate } from "@/src/features/production/types";
import type { OwnedChannel } from "@/src/features/production/types";
import {
  InlineError,
  primaryButton,
  textareaClass,
} from "@/src/features/production/ui";

const lines = (value: unknown[]) => value.map(String).join("\n");

export function ChannelDetailPage({
  workspaceId,
  channelId,
}: {
  workspaceId: string;
  channelId: string;
}) {
  const channel = useChannel(workspaceId, channelId);
  const permission = useWorkspaceRole(workspaceId);

  if (channel.isLoading) return <p>正在加载账号定位…</p>;
  if (channel.error)
    return <ErrorState message="账号定位加载失败。" onRetry={() => channel.refetch()} />;
  return (
    <ChannelForm
      channel={channel.data!}
      canEdit={permission.canEdit}
      workspaceId={workspaceId}
    />
  );
}

function ChannelForm({
  channel,
  canEdit,
  workspaceId,
}: {
  channel: OwnedChannel;
  canEdit: boolean;
  workspaceId: string;
}) {
  const save = useSavePositioning(workspaceId, channel.id);
  const [form, setForm] = useState<PositioningUpdate>({
    positioning: channel.positioning,
    audience: channel.audience,
    content_pillars: channel.content_pillars.map(String),
    tone_rules: channel.tone_rules.map(String),
    prohibited_topics: channel.prohibited_topics.map(String),
  });
  const [audienceText, setAudienceText] = useState(
    JSON.stringify(channel.audience, null, 2),
  );
  return (
    <>
      <PageHeader
        eyebrow="账号定位"
        title={channel.display_name}
        description={`${channel.platform} · ${channel.handle || "未设置账号标识"} · ${channel.publishing_mode === "manual" ? "人工发布" : channel.publishing_mode}`}
        actions={
          <Link className="inline-flex items-center gap-2 text-sm text-text-muted" href={`/w/${workspaceId}/channels`}>
            <ArrowLeft size={15} /> 返回账号
          </Link>
        }
      />
      <form
        className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_340px]"
        onSubmit={(event) => {
          event.preventDefault();
          let audience = form.audience;
          try {
            audience = JSON.parse(audienceText);
          } catch {
            return;
          }
          save.mutate({ ...form, audience });
        }}
      >
        <section className="space-y-5 rounded-xl border border-border bg-surface p-5 shadow-panel">
          <label className="block text-sm font-medium">
            定位声明
            <textarea
              className={`${textareaClass} mt-2 min-h-32`}
              disabled={!canEdit}
              onChange={(event) => setForm({ ...form, positioning: event.target.value })}
              value={form.positioning}
            />
          </label>
          <label className="block text-sm font-medium">
            目标受众（JSON）
            <textarea
              className={`${textareaClass} mt-2 font-mono text-xs`}
              disabled={!canEdit}
              onChange={(event) => setAudienceText(event.target.value)}
              value={audienceText}
            />
          </label>
          {[
            ["内容支柱", "content_pillars"],
            ["语气与表达规则", "tone_rules"],
            ["禁区与事实核查", "prohibited_topics"],
          ].map(([label, key]) => (
            <label className="block text-sm font-medium" key={key}>
              {label}
              <textarea
                className={`${textareaClass} mt-2`}
                disabled={!canEdit}
                onChange={(event) =>
                  setForm({
                    ...form,
                    [key]: event.target.value
                      .split("\n")
                      .map((item) => item.trim())
                      .filter(Boolean),
                  })
                }
                placeholder="每行一条"
                value={lines(form[key as keyof PositioningUpdate] as unknown[])}
              />
            </label>
          ))}
          <InlineError error={save.error} />
          {save.isSuccess ? (
            <p className="text-xs font-medium text-success">定位规则已保存并用于后续生成。</p>
          ) : null}
          {canEdit ? (
            <button className={primaryButton} disabled={save.isPending} type="submit">
              <Save size={15} /> 保存定位
            </button>
          ) : null}
        </section>
        <aside className="space-y-4">
          <div className="rounded-xl border border-border bg-surface p-5">
            <h2 className="text-sm font-semibold">生成约束预览</h2>
            <p className="mt-2 text-xs leading-5 text-text-muted">
              AI 脚本会引用定位、内容支柱和语气规则；禁区永远需要人工复核。
            </p>
          </div>
          <div className="rounded-xl border border-amber-200 bg-amber-50 p-5 text-amber-900">
            <p className="flex items-center gap-2 text-sm font-semibold">
              <ShieldAlert size={16} /> 事实核查责任
            </p>
            <p className="mt-2 text-xs leading-5">
              定位规则不能替代审核。涉及价格、效果、客户案例与第三方数据时，发布前必须核验来源。
            </p>
          </div>
        </aside>
      </form>
    </>
  );
}
