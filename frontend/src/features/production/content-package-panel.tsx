"use client";

import {
  Bot,
  Film,
  Pencil,
  Save,
  Snowflake,
  Sparkles,
  Unlock,
} from "lucide-react";
import { useMemo, useState } from "react";
import { ErrorState } from "@/src/components/ui/error-state";
import {
  useContentPackages,
  useEditContentPackage,
  useFreezeContentPackage,
  useGenerateContentPackage,
} from "@/src/features/production/queries";
import type {
  ContentPackage,
  ContentPackagePayload,
  ContentPackageScene,
  ScriptVersion,
} from "@/src/features/production/types";
import {
  InlineError,
  inputClass,
  primaryButton,
  secondaryButton,
  textareaClass,
} from "@/src/features/production/ui";

const PLATFORM_LABELS: Record<string, string> = {
  xiaohongshu: "小红书",
  douyin: "抖音",
  video: "视频号",
};

const LAYOUT_LABELS: Record<string, string> = {
  avatar_full: "全屏口播",
  avatar_corner: "角落口播",
  broll: "B  Roll",
  comparison: "对比",
  cta: "CTA",
};

type EditableScene = Omit<ContentPackageScene, "on_screen_text"> & {
  on_screen_text: string;
};

function asPayload(pkg: ContentPackage): ContentPackagePayload {
  return pkg.package as unknown as ContentPackagePayload;
}

function hasEmoji(text: string) {
  return /\p{Extended_Pictographic}/u.test(text);
}

function SceneBadge({ layout }: { layout: string }) {
  return (
    <span className="rounded bg-surface-subtle px-1.5 py-0.5 text-[10px] font-medium text-text-muted">
      {LAYOUT_LABELS[layout] ?? layout}
    </span>
  );
}

export function ContentPackagePanel({
  workspaceId,
  projectId,
  project,
  scripts,
  canEdit,
}: {
  workspaceId: string;
  projectId: string;
  project: { id: string; version: number; title: string };
  scripts: ScriptVersion[];
  canEdit: boolean;
}) {
  const packages = useContentPackages(workspaceId, projectId);
  const generate = useGenerateContentPackage(workspaceId, projectId);
  const edit = useEditContentPackage(workspaceId, projectId);
  const freeze = useFreezeContentPackage(workspaceId, projectId);
  const orderedScripts = useMemo(
    () => scripts.slice().sort((a, b) => b.version_no - a.version_no),
    [scripts],
  );
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [scriptVersionId, setScriptVersionId] = useState(
    orderedScripts[0]?.id ?? "",
  );
  const [platform, setPlatform] = useState("xiaohongshu");
  const [editing, setEditing] = useState(false);

  const items = (packages.data ?? []).slice().sort(
    (a, b) =>
      b.created_at.localeCompare(a.created_at) ||
      b.version - a.version,
  );
  const selected =
    items.find((item) => item.id === selectedId) ?? items[0] ?? null;
  const payload = selected ? asPayload(selected) : null;

  if (packages.isLoading) return <p>正在加载内容包…</p>;
  if (packages.error) {
    return (
      <ErrorState
        message="内容包加载失败。"
        onRetry={() => packages.refetch()}
      />
    );
  }

  return (
    <div className="grid gap-4 xl:grid-cols-[300px_minmax(0,1fr)]">
      <aside className="space-y-4">
        <section className="rounded-xl border border-border bg-surface p-5 shadow-panel">
          <p className="flex items-center gap-2 text-sm font-semibold">
            <Film size={16} /> 生成内容包
          </p>
          <p className="mt-2 text-xs leading-5 text-text-muted">
            从已定稿脚本生成完整成片素材：分镜、字幕、标题、封面、话题与素材清单。
          </p>
          <label className="mt-3 block text-[11px] font-medium">
            脚本版本
            <select
              className={`${inputClass} mt-1 min-h-9`}
              disabled={!orderedScripts.length}
              onChange={(event) => setScriptVersionId(event.target.value)}
              value={scriptVersionId}
            >
              {orderedScripts.map((script) => (
                <option key={script.id} value={script.id}>
                  v{script.version_no} ·{" "}
                  {script.generation_run_id ? "AI" : "人工"}
                  {script.change_note
                    ? ` · ${script.change_note.slice(0, 20)}`
                    : ""}
                </option>
              ))}
            </select>
          </label>
          <label className="mt-3 block text-[11px] font-medium">
            目标平台
            <select
              className={`${inputClass} mt-1 min-h-9`}
              onChange={(event) => setPlatform(event.target.value)}
              value={platform}
            >
              {Object.entries(PLATFORM_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <button
            className={`${primaryButton} mt-3 w-full`}
            disabled={
              !scriptVersionId || generate.isPending || !canEdit
            }
            onClick={() =>
              generate.mutate({
                project_version: project.version,
                script_version_id: scriptVersionId,
                target_platform: platform,
                force: false,
              })
            }
            type="button"
          >
            <Sparkles size={15} /> 创建生成任务
          </button>
          {generate.isSuccess ? (
            <p className="mt-2 rounded-lg bg-primary-50 p-2.5 text-[11px] leading-5 text-primary-700">
              生成任务已进入队列，完成后刷新本页查看内容包。
            </p>
          ) : null}
          <InlineError error={generate.error} />
        </section>

        <section className="rounded-xl border border-border bg-surface p-4">
          <p className="px-1 pb-2 text-xs font-semibold">内容包列表</p>
          {items.length ? (
            <div className="space-y-1.5">
              {items.map((item) => (
                <button
                  className={`w-full rounded-lg p-3 text-left text-xs ${
                    selected?.id === item.id
                      ? "bg-primary-50 text-primary-700"
                      : "hover:bg-surface-subtle"
                  }`}
                  key={item.id}
                  onClick={() => {
                    setSelectedId(item.id);
                    setEditing(false);
                  }}
                  type="button"
                >
                  <strong className="flex items-center justify-between gap-2">
                    <span>
                      {PLATFORM_LABELS[item.target_platform] ??
                        item.target_platform}{" "}
                      · v{item.version}
                    </span>
                    <span
                      className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${
                        item.status === "frozen"
                          ? "bg-success/10 text-success"
                          : "bg-surface-subtle text-text-muted"
                      }`}
                    >
                      {item.status === "frozen" ? "已冻结" : "草稿"}
                    </span>
                  </strong>
                  <span className="mt-1 block truncate text-text-muted">
                    {asPayload(item).scenes.length} 个分镜 ·{" "}
                    {asPayload(item).target_duration_seconds} 秒
                  </span>
                </button>
              ))}
            </div>
          ) : (
            <p className="px-1 py-3 text-xs leading-5 text-text-muted">
              还没有内容包。选好脚本版本后点击「创建生成任务」。
            </p>
          )}
        </section>
      </aside>

      <section className="min-w-0 rounded-xl border border-border bg-surface p-5 shadow-panel">
        {selected && payload ? (
          editing ? (
            <PackageEditor
              canEdit={canEdit}
              edit={edit}
              onCancel={() => setEditing(false)}
              onSaved={(savedId) => setSelectedId(savedId)}
              pkg={selected}
              payload={payload}
            />
          ) : (
            <PackageDetail
              canEdit={canEdit}
              freeze={freeze}
              onEdit={() => setEditing(true)}
              pkg={selected}
              payload={payload}
            />
          )
        ) : (
          <div className="flex h-64 items-center justify-center text-sm text-text-muted">
            <Bot aria-hidden className="mr-2" size={18} />
            生成后这里会展示分镜、标题与素材清单
          </div>
        )}
      </section>
    </div>
  );
}

function PackageDetail({
  pkg,
  payload,
  canEdit,
  onEdit,
  freeze,
}: {
  pkg: ContentPackage;
  payload: ContentPackagePayload;
  canEdit: boolean;
  onEdit: () => void;
  freeze: ReturnType<typeof useFreezeContentPackage>;
}) {
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-border pb-4">
        <div>
          <p className="flex items-center gap-2 text-sm font-semibold">
            {PLATFORM_LABELS[pkg.target_platform] ?? pkg.target_platform} 内容包
            <span
              className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${
                pkg.status === "frozen"
                  ? "bg-success/10 text-success"
                  : "bg-surface-subtle text-text-muted"
              }`}
            >
              {pkg.status === "frozen" ? "已冻结" : "草稿"}
            </span>
          </p>
          <p className="mt-1 text-xs text-text-muted">
            v{pkg.version} · {payload.scenes.length} 个分镜 · 预计{" "}
            {payload.target_duration_seconds}s ·{" "}
            {payload.narration.spoken_length_chars} 字口播
          </p>
        </div>
        <div className="flex gap-2">
          {canEdit ? (
            <button
              className={secondaryButton}
              onClick={onEdit}
              type="button"
            >
              <Pencil size={14} /> 编辑为新版本
            </button>
          ) : null}
          {canEdit && pkg.status !== "frozen" ? (
            <button
              className={secondaryButton}
              disabled={freeze.isPending}
              onClick={() => freeze.mutate(pkg.id)}
              type="button"
            >
              <Snowflake size={14} /> 冻结
            </button>
          ) : null}
        </div>
      </div>

      <div>
        <p className="text-xs font-semibold">分镜</p>
        <div className="mt-2 space-y-3">
          {payload.scenes.map((scene) => (
            <article
              className="rounded-lg border border-border p-4"
              key={scene.id}
            >
              <div className="flex flex-wrap items-center gap-2 text-[11px] text-text-muted">
                <SceneBadge layout={scene.layout} />
                <span>{scene.estimated_seconds}s</span>
                <span>{scene.id}</span>
              </div>
              <p className="mt-2 text-sm leading-6">{scene.narration_chunk}</p>
              {scene.on_screen_text ? (
                <p className="mt-2 inline-block rounded bg-surface-subtle px-2 py-1 text-xs text-primary-700">
                  屏显：{scene.on_screen_text}
                </p>
              ) : null}
              <p className="mt-2 text-xs text-text-muted">
                画面：{scene.visual_hint}
              </p>
              {scene.asset_queries?.length ? (
                <p className="mt-1 text-[11px] text-text-muted">
                  素材：{scene.asset_queries.join("、")}
                </p>
              ) : null}
              {scene.cta ? (
                <p className="mt-2 text-xs font-medium text-primary-700">
                  CTA：{scene.cta}
                </p>
              ) : null}
            </article>
          ))}
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-lg border border-border p-4">
          <p className="text-xs font-semibold">标题候选</p>
          <ul className="mt-2 space-y-1.5 text-sm">
            {payload.title_candidates.map((title, index) => (
              <li key={`${title.text}-${index}`} className="flex items-start gap-2">
                <span className="mt-0.5 rounded bg-surface-subtle px-1.5 text-[10px] text-text-muted">
                  {index + 1}
                </span>
                <span>{title.text}</span>
              </li>
            ))}
          </ul>
        </div>
        <div className="rounded-lg border border-border p-4">
          <p className="text-xs font-semibold">封面</p>
          <p className="mt-2 text-sm font-medium">{payload.cover.headline}</p>
          {payload.cover.subheadline ? (
            <p className="mt-1 text-xs text-text-muted">
              {payload.cover.subheadline}
            </p>
          ) : null}
          {payload.cover.visual_hint ? (
            <p className="mt-2 text-xs leading-5 text-text-muted">
              {payload.cover.visual_hint}
            </p>
          ) : null}
        </div>
      </div>

      <div className="rounded-lg border border-border p-4">
        <p className="text-xs font-semibold">发布文案与话题</p>
        <p className="mt-2 text-sm leading-6">{payload.publish_caption}</p>
        <p className="mt-2 text-xs text-primary-700">
          {payload.hashtags.join(" ")}
        </p>
      </div>

      {payload.assets_required.length ? (
        <div className="rounded-lg border border-border p-4">
          <p className="text-xs font-semibold">素材需求</p>
          <ul className="mt-2 space-y-2 text-xs leading-5">
            {payload.assets_required.map((asset, index) => (
              <li key={`${asset.query}-${index}`}>
                <strong>{asset.kind}：</strong>
                {asset.query}
                {asset.rights_note ? (
                  <span className="block text-text-muted">
                    权利说明：{asset.rights_note}
                  </span>
                ) : null}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-lg border border-border p-4">
          <p className="text-xs font-semibold">配音与音乐</p>
          <p className="mt-2 text-xs leading-5 text-text-muted">
            {payload.audio.voice_hint}
          </p>
          {payload.audio.music_mood ? (
            <p className="mt-1 text-xs text-text-muted">
              BGM：{payload.audio.music_mood}
              {payload.audio.music_ducking
                ? `（口播时 ${payload.audio.music_ducking}）`
                : ""}
            </p>
          ) : null}
        </div>
        <div className="rounded-lg border border-border p-4">
          <p className="text-xs font-semibold">发布时间建议</p>
          <p className="mt-2 text-xs leading-5 text-text-muted">
            {payload.publish_timing_hint ?? "未提供"}
          </p>
        </div>
      </div>
    </div>
  );
}

function PackageEditor({
  pkg,
  payload,
  canEdit,
  onCancel,
  onSaved,
  edit,
}: {
  pkg: ContentPackage;
  payload: ContentPackagePayload;
  canEdit: boolean;
  onCancel: () => void;
  onSaved: (packageId: string) => void;
  edit: ReturnType<typeof useEditContentPackage>;
}) {
  const [titles, setTitles] = useState(
    payload.title_candidates.map((item) => item.text),
  );
  const [hashtags, setHashtags] = useState(payload.hashtags.join(" "));
  const [caption, setCaption] = useState(payload.publish_caption);
  const [scenes, setScenes] = useState(
    payload.scenes.map((scene) => ({
      ...scene,
      on_screen_text: scene.on_screen_text ?? "",
    })) as EditableScene[],
  );

  function updateScene(
    index: number,
    patch: Partial<EditableScene>,
  ) {
    setScenes((current) =>
      current.map((scene, sceneIndex) =>
        sceneIndex === index ? { ...scene, ...patch } : scene,
      ),
    );
  }

  function save() {
    const cleanedTitles = titles
      .map((text) => text.trim())
      .filter(Boolean)
      .map((text) => ({
        text,
        length_chars: [...text].length,
        has_emoji: hasEmoji(text),
      }));
    if (!cleanedTitles.length) return;
    edit.mutate(
      {
        packageId: pkg.id,
        input: {
          title_candidates: cleanedTitles,
          hashtags: hashtags
            .split(/[\s,#，]+/)
            .map((item) => item.trim())
            .filter(Boolean),
          publish_caption: caption.trim(),
          scenes: scenes.map((scene) => ({
            ...scene,
            on_screen_text: scene.on_screen_text?.trim() || null,
          })),
        },
      },
      {
        onSuccess: (updated) => {
          onSaved(updated.id);
          onCancel();
        },
      },
    );
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between border-b border-border pb-4">
        <div>
          <p className="text-sm font-semibold">
            编辑内容包 · v{pkg.version} 之后的新版本
          </p>
          <p className="mt-1 text-xs text-text-muted">
            保存会追加一个新版本，原版本保留。
          </p>
        </div>
        <div className="flex gap-2">
          <button className={secondaryButton} onClick={onCancel} type="button">
            <Unlock size={14} /> 取消
          </button>
          <button
            className={primaryButton}
            disabled={!canEdit || edit.isPending}
            onClick={save}
            type="button"
          >
            <Save size={14} /> 保存为新版本
          </button>
        </div>
      </div>

      <div>
        <p className="text-xs font-semibold">分镜（屏显/秒数/画面可改）</p>
        <div className="mt-2 space-y-3">
          {scenes.map((scene, index) => (
            <div
              className="rounded-lg border border-border p-4"
              key={scene.id}
            >
              <div className="flex flex-wrap items-center gap-2 text-[11px] text-text-muted">
                <SceneBadge layout={scene.layout} />
                <span>{scene.id}</span>
                <span>{scene.estimated_seconds}s</span>
              </div>
              <p className="mt-2 text-sm leading-6">{scene.narration_chunk}</p>
              <div className="mt-3 grid gap-2 sm:grid-cols-2">
                <label className="block text-[11px] font-medium">
                  屏显文字
                  <input
                    className={`${inputClass} mt-1 min-h-9`}
                    onChange={(event) =>
                      updateScene(index, {
                        on_screen_text: event.target.value,
                      })
                    }
                    value={scene.on_screen_text ?? ""}
                  />
                </label>
                <label className="block text-[11px] font-medium">
                  时长（秒）
                  <input
                    className={`${inputClass} mt-1 min-h-9`}
                    min={1}
                    onChange={(event) =>
                      updateScene(index, {
                        estimated_seconds: Number(event.target.value),
                      })
                    }
                    type="number"
                    value={scene.estimated_seconds}
                  />
                </label>
              </div>
              <label className="mt-2 block text-[11px] font-medium">
                画面提示
                <textarea
                  className={`${textareaClass} mt-1 min-h-16`}
                  onChange={(event) =>
                    updateScene(index, { visual_hint: event.target.value })
                  }
                  value={scene.visual_hint}
                />
              </label>
            </div>
          ))}
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-lg border border-border p-4">
          <p className="text-xs font-semibold">标题候选（最多 3 个）</p>
          <div className="mt-2 space-y-2">
            {[0, 1, 2].map((index) => (
              <input
                className={`${inputClass} min-h-9`}
                key={index}
                onChange={(event) =>
                  setTitles((current) =>
                    current.map((text, titleIndex) =>
                      titleIndex === index ? event.target.value : text,
                    ),
                  )
                }
                placeholder={`标题候选 ${index + 1}`}
                value={titles[index] ?? ""}
              />
            ))}
          </div>
        </div>
        <div className="rounded-lg border border-border p-4">
          <label className="block text-xs font-semibold">
            话题标签（空格分隔）
            <input
              className={`${inputClass} mt-2 min-h-9`}
              onChange={(event) => setHashtags(event.target.value)}
              placeholder="#内容运营 #脚本"
              value={hashtags}
            />
          </label>
          <label className="mt-3 block text-xs font-semibold">
            发布文案
            <textarea
              className={`${textareaClass} mt-2 min-h-28`}
              onChange={(event) => setCaption(event.target.value)}
              value={caption}
            />
          </label>
        </div>
      </div>

      <InlineError error={edit.error} />
    </div>
  );
}
