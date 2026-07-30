"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { LoaderCircle, Plus, X } from "lucide-react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { useCreateTrackedProfile } from "@/src/features/tracked-profiles/queries";

const schema = z.object({
  display_name: z.string().min(1, "请输入账号名称").max(255),
  platform: z.enum([
    "xiaohongshu",
    "douyin",
    "bilibili",
    "youtube",
    "wechat_channels",
    "tiktok",
    "instagram",
  ]),
  profile_url: z.url("请输入有效的主页链接"),
  external_id: z.string().min(1, "请输入平台账号 ID"),
  handle: z.string().max(255).optional(),
  priority: z.number().min(0).max(100),
});

type FormValues = z.infer<typeof schema>;

export function CreateProfileDialog({
  open,
  onClose,
  workspaceId,
}: {
  open: boolean;
  onClose: () => void;
  workspaceId: string;
}) {
  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      display_name: "",
      platform: "xiaohongshu",
      profile_url: "",
      external_id: "",
      handle: "",
      priority: 50,
    },
  });
  const create = useCreateTrackedProfile(workspaceId, () => {
    form.reset();
    onClose();
  });

  if (!open) return null;

  return (
    <div
      aria-labelledby="create-profile-title"
      aria-modal="true"
      className="fixed inset-0 z-[70] flex justify-end bg-text/30 backdrop-blur-sm"
      role="dialog"
    >
      <button
        aria-label="关闭新建账号"
        className="absolute inset-0"
        onClick={onClose}
        type="button"
      />
      <div className="relative flex h-full w-full max-w-lg flex-col border-l border-border bg-surface shadow-popover">
        <header className="flex items-start justify-between border-b border-border px-6 py-5">
          <div>
            <p className="text-xs font-semibold tracking-[0.14em] text-primary-600 uppercase">
              Tracked profile
            </p>
            <h2 className="mt-1 text-xl font-semibold" id="create-profile-title">
              新建对标账号
            </h2>
            <p className="mt-1 text-sm text-text-muted">
              添加后可单独发起同步任务，不会自动产生费用。
            </p>
          </div>
          <button
            aria-label="关闭"
            className="grid size-9 place-items-center rounded-lg text-text-muted hover:bg-surface-subtle"
            onClick={onClose}
            type="button"
          >
            <X aria-hidden="true" size={18} />
          </button>
        </header>

        <form
          className="scrollbar-subtle flex flex-1 flex-col overflow-y-auto"
          onSubmit={form.handleSubmit((values) =>
            create.mutate({
              ...values,
              handle: values.handle || null,
            }),
          )}
        >
          <div className="flex-1 space-y-5 p-6">
            <Field label="账号名称" error={form.formState.errors.display_name?.message}>
              <input
                className="h-11 w-full rounded-lg border border-border bg-surface px-3 text-sm outline-none focus:border-primary-500"
                placeholder="例如：海盐商业笔记"
                {...form.register("display_name")}
              />
            </Field>

            <div className="grid gap-5 sm:grid-cols-2">
              <Field label="平台" error={form.formState.errors.platform?.message}>
                <select
                  className="h-11 w-full rounded-lg border border-border bg-surface px-3 text-sm outline-none focus:border-primary-500"
                  {...form.register("platform")}
                >
                  <option value="xiaohongshu">小红书</option>
                  <option value="douyin">抖音</option>
                  <option value="bilibili">哔哩哔哩</option>
                  <option value="youtube">YouTube</option>
                  <option value="wechat_channels">视频号</option>
                  <option value="tiktok">TikTok</option>
                  <option value="instagram">Instagram</option>
                </select>
              </Field>
              <Field label="优先级" error={form.formState.errors.priority?.message}>
                <input
                  className="h-11 w-full rounded-lg border border-border bg-surface px-3 text-sm outline-none focus:border-primary-500"
                  min={0}
                  max={100}
                  type="number"
                  {...form.register("priority", { valueAsNumber: true })}
                />
              </Field>
            </div>

            <Field label="主页链接" error={form.formState.errors.profile_url?.message}>
              <input
                className="h-11 w-full rounded-lg border border-border bg-surface px-3 text-sm outline-none focus:border-primary-500"
                placeholder="https://..."
                type="url"
                {...form.register("profile_url")}
              />
            </Field>

            <Field
              label="平台账号 ID"
              hint="用于去重，暂不从链接中自动猜测。"
              error={form.formState.errors.external_id?.message}
            >
              <input
                className="h-11 w-full rounded-lg border border-border bg-surface px-3 text-sm outline-none focus:border-primary-500"
                placeholder="平台内稳定的账号标识"
                {...form.register("external_id")}
              />
            </Field>

            <Field label="账号 Handle（可选）" error={form.formState.errors.handle?.message}>
              <input
                className="h-11 w-full rounded-lg border border-border bg-surface px-3 text-sm outline-none focus:border-primary-500"
                placeholder="@handle"
                {...form.register("handle")}
              />
            </Field>

            {create.error ? (
              <div className="rounded-lg border border-red-100 bg-red-50 px-4 py-3 text-sm text-red-700">
                {(create.error as { message?: string }).message ??
                  "创建失败，请检查输入后重试。"}
              </div>
            ) : null}
          </div>

          <footer className="sticky bottom-0 flex justify-end gap-2 border-t border-border bg-surface px-6 py-4">
            <button
              className="rounded-lg border border-border px-4 py-2.5 text-sm font-medium hover:bg-surface-subtle"
              onClick={onClose}
              type="button"
            >
              取消
            </button>
            <button
              className="inline-flex min-w-28 items-center justify-center gap-2 rounded-lg bg-primary-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-primary-700 disabled:cursor-not-allowed disabled:opacity-60"
              disabled={create.isPending}
              type="submit"
            >
              {create.isPending ? (
                <LoaderCircle aria-hidden="true" className="animate-spin" size={16} />
              ) : (
                <Plus aria-hidden="true" size={16} />
              )}
              添加账号
            </button>
          </footer>
        </form>
      </div>
    </div>
  );
}

function Field({
  label,
  hint,
  error,
  children,
}: {
  label: string;
  hint?: string;
  error?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="mb-2 block text-sm font-medium">{label}</span>
      {children}
      {error ? (
        <span className="mt-1.5 block text-xs text-danger">{error}</span>
      ) : hint ? (
        <span className="mt-1.5 block text-xs text-text-muted">{hint}</span>
      ) : null}
    </label>
  );
}
