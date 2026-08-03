"use client";

import { ArrowLeft, Bot, Copy, Save, Sparkles } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";
import { ErrorState } from "@/src/components/ui/error-state";
import { PageHeader } from "@/src/components/ui/page-header";
import { useWorkspaceRole } from "@/src/features/identity/queries";
import { ContentPackagePanel } from "@/src/features/production/content-package-panel";
import {
  useGenerateScript,
  useProject,
  useSaveScript,
  useScripts,
} from "@/src/features/production/queries";
import type {
  ContentProject,
  ScriptVersion,
} from "@/src/features/production/types";
import {
  InlineError,
  inputClass,
  primaryButton,
  secondaryButton,
  textareaClass,
} from "@/src/features/production/ui";

export function ScriptPage({
  workspaceId,
  projectId,
}: {
  workspaceId: string;
  projectId: string;
}) {
  const project = useProject(workspaceId, projectId);
  const scripts = useScripts(workspaceId, projectId);
  const permission = useWorkspaceRole(workspaceId);
  if (project.isLoading || scripts.isLoading) return <p>正在加载脚本工作台…</p>;
  if (project.error || scripts.error || !project.data) {
    return (
      <ErrorState
        message="脚本工作台加载失败。"
        onRetry={() => {
          project.refetch();
          scripts.refetch();
        }}
      />
    );
  }
  return (
    <ScriptEditor
      canEdit={permission.canEdit}
      initialScripts={scripts.data ?? []}
      project={project.data}
      workspaceId={workspaceId}
    />
  );
}

function ScriptEditor({
  workspaceId,
  project,
  initialScripts,
  canEdit,
}: {
  workspaceId: string;
  project: ContentProject;
  initialScripts: ScriptVersion[];
  canEdit: boolean;
}) {
  const ordered = useMemo(
    () => initialScripts.slice().sort((a, b) => b.version_no - a.version_no),
    [initialScripts],
  );
  const save = useSaveScript(workspaceId, project.id);
  const generate = useGenerateScript(workspaceId, project.id);
  const [selected, setSelected] = useState<number | null>(
    ordered[0]?.version_no ?? null,
  );
  const initial = ordered.find((item) => item.version_no === selected) ?? ordered[0];
  const [body, setBody] = useState(initial?.body ?? "");
  const [note, setNote] = useState("");
  const [instruction, setInstruction] = useState("");
  const [tab, setTab] = useState<"script" | "package">("script");
  const active = ordered.find((item) => item.version_no === selected) ?? initial;
  const dirty = body !== (active?.body ?? "");
  const conflict =
    save.error &&
    /冲突|版本|changed|conflict/i.test((save.error as Error).message);

  return (
    <>
      <PageHeader
        actions={
          <Link
            className={secondaryButton}
            href={`/w/${workspaceId}/content-projects/${project.id}`}
          >
            <ArrowLeft size={15} /> 返回项目
          </Link>
        }
        description="左侧版本、中间编辑、右侧生成依据。保存永远追加版本；冲突时本地草稿不会被清空。"
        eyebrow="脚本工作台"
        title={project.title}
      />
      <div className="mb-4 flex gap-1 rounded-xl border border-border bg-surface p-1 shadow-panel">
        <button
          className={`flex-1 rounded-lg px-4 py-2 text-sm font-medium ${
            tab === "script"
              ? "bg-primary-50 text-primary-700"
              : "text-text-muted hover:bg-surface-subtle"
          }`}
          onClick={() => setTab("script")}
          type="button"
        >
          脚本编辑
        </button>
        <button
          className={`flex-1 rounded-lg px-4 py-2 text-sm font-medium ${
            tab === "package"
              ? "bg-primary-50 text-primary-700"
              : "text-text-muted hover:bg-surface-subtle"
          }`}
          onClick={() => setTab("package")}
          type="button"
        >
          内容包
        </button>
      </div>
      {tab === "package" ? (
        <ContentPackagePanel
          canEdit={canEdit}
          project={project}
          projectId={project.id}
          scripts={initialScripts}
          workspaceId={workspaceId}
        />
      ) : null}
      {conflict ? (
        <div className="mb-4 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
          <strong>检测到版本冲突，本地草稿已保留。</strong>
          <p className="mt-1 text-xs">
            复制草稿后刷新版本列表，或确认最新项目版本再重新保存。
          </p>
          <button
            className={`${secondaryButton} mt-3`}
            onClick={() => navigator.clipboard.writeText(body)}
            type="button"
          >
            <Copy size={14} /> 复制本地草稿
          </button>
        </div>
      ) : null}
      {generate.isSuccess ? (
        <div className="mb-4 rounded-xl border border-primary-100 bg-primary-50 p-4 text-sm text-primary-700">
          生成任务已进入队列（Job {generate.data.jobId.slice(0, 8)}…）。完成后刷新版本列表；当前草稿不受影响。
        </div>
      ) : null}
      {tab === "script" ? (
      <div className="grid gap-4 xl:grid-cols-[230px_minmax(0,1fr)_300px]">
        <aside className="rounded-xl border border-border bg-surface p-3">
          <p className="px-2 py-2 text-xs font-semibold">版本历史</p>
          <div className="space-y-1">
            {ordered.map((script) => (
              <button
                className={`w-full rounded-lg p-3 text-left text-xs ${
                  selected === script.version_no
                    ? "bg-primary-50 text-primary-700"
                    : "hover:bg-surface-subtle"
                }`}
                key={script.id}
                onClick={() => {
                  if (
                    !dirty ||
                    confirm("切换版本会放弃当前未保存内容，继续吗？")
                  ) {
                    setSelected(script.version_no);
                    setBody(script.body);
                  }
                }}
                type="button"
              >
                <strong className="block">
                  v{script.version_no} · {script.generation_run_id ? "AI" : "人工"}
                </strong>
                <span className="mt-1 block truncate text-text-muted">
                  {script.change_note || "无修改说明"}
                </span>
              </button>
            ))}
          </div>
        </aside>
        <section className="rounded-xl border border-border bg-surface p-5 shadow-panel">
          <div className="mb-3 flex items-center justify-between">
            <p className="text-xs font-semibold">当前草稿</p>
            {dirty ? (
              <span className="text-[11px] font-medium text-warning">尚未保存</span>
            ) : (
              <span className="text-[11px] text-text-muted">已同步</span>
            )}
          </div>
          <textarea
            className={`${textareaClass} min-h-[480px] resize-y leading-7`}
            disabled={!canEdit}
            onChange={(event) => setBody(event.target.value)}
            value={body}
          />
          <input
            className={`${inputClass} mt-3`}
            disabled={!canEdit}
            onChange={(event) => setNote(event.target.value)}
            placeholder="修改说明（建议填写）"
            value={note}
          />
          <InlineError error={save.error} />
          {canEdit ? (
            <button
              className={`${primaryButton} mt-3`}
              disabled={!body.trim() || save.isPending}
              onClick={() =>
                save.mutate(
                  {
                    project_version: project.version,
                    body,
                    structured_body: active?.structured_body ?? null,
                    change_note: note || "人工编辑",
                  },
                  {
                    onSuccess: (created) => {
                      setSelected(created.version_no);
                      setBody(created.body);
                      setNote("");
                    },
                  },
                )
              }
              type="button"
            >
              <Save size={15} /> 保存为新版本
            </button>
          ) : null}
        </section>
        <aside className="space-y-4">
          <div className="rounded-xl border border-border bg-surface p-5">
            <p className="flex items-center gap-2 text-sm font-semibold">
              <Bot size={16} /> AI 生成新版本
            </p>
            <p className="mt-2 text-xs leading-5 text-text-muted">
              会引用账号定位与项目上下文。接口接受后返回异步生成任务，不伪装为脚本已经完成。
            </p>
            <textarea
              className={`${textareaClass} mt-3 min-h-24`}
              onChange={(event) => setInstruction(event.target.value)}
              placeholder="补充生成要求…"
              value={instruction}
            />
            <button
              className={`${secondaryButton} mt-3 w-full`}
              disabled={generate.isPending}
              onClick={() =>
                generate.mutate({
                  projectVersion: project.version,
                  instruction,
                })
              }
              type="button"
            >
              <Sparkles size={15} /> 创建生成任务
            </button>
            <InlineError error={generate.error} />
          </div>
          <div className="rounded-xl border border-border bg-surface p-5">
            <p className="text-sm font-semibold">当前版本依据</p>
            <dl className="mt-3 space-y-2 text-xs">
              <div className="flex justify-between">
                <dt className="text-text-muted">来源</dt>
                <dd>{active?.generation_run_id ? "AI 生成" : "人工创建"}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-text-muted">结构化脚本</dt>
                <dd>{active?.structured_body ? "有" : "无"}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-text-muted">版本号</dt>
                <dd>v{active?.version_no ?? "—"}</dd>
              </div>
            </dl>
          </div>
        </aside>
      </div>
      ) : null}
    </>
  );
}
