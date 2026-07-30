"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowRight, LoaderCircle } from "lucide-react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { AuthShell } from "@/src/features/identity/auth-shell";
import { useCreateWorkspace } from "@/src/features/identity/queries";

const schema = z.object({
  name: z.string().min(1, "请输入工作区名称").max(255),
  timezone: z.string().min(1),
  daily_provider_budget_usd: z.number().min(0).max(1000),
  daily_ai_budget_usd: z.number().min(0).max(1000),
});

type Values = z.infer<typeof schema>;

export function CreateWorkspacePage() {
  const router = useRouter();
  const create = useCreateWorkspace();
  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: {
      name: "增长实验室",
      timezone: "Australia/Melbourne",
      daily_provider_budget_usd: 5,
      daily_ai_budget_usd: 5,
    },
  });

  return (
    <AuthShell
      description="工作区是账号、任务、预算与成员权限的隔离边界。创建后系统会自动生成一套可调整的默认扫描策略。"
      eyebrow="Workspace"
      title="创建第一个工作区"
    >
      <form
        className="rounded-2xl border border-border bg-surface p-6 shadow-panel sm:p-8"
        onSubmit={form.handleSubmit((values) =>
          create.mutate(values, {
            onSuccess: (workspace) =>
              router.push(`/w/${workspace.id}/today`),
          }),
        )}
      >
        <FormField
          error={form.formState.errors.name?.message}
          label="工作区名称"
        >
          <input
            className="h-11 w-full rounded-lg border border-border px-3 text-sm outline-none focus:border-primary-500"
            {...form.register("name")}
          />
        </FormField>

        <FormField label="时区">
          <select
            className="h-11 w-full rounded-lg border border-border bg-surface px-3 text-sm outline-none focus:border-primary-500"
            {...form.register("timezone")}
          >
            <option value="Australia/Melbourne">Australia/Melbourne</option>
            <option value="Asia/Shanghai">Asia/Shanghai</option>
            <option value="UTC">UTC</option>
          </select>
        </FormField>

        <div className="grid grid-cols-2 gap-4">
          <FormField label="数据日预算（USD）">
            <input
              className="h-11 w-full rounded-lg border border-border px-3 text-sm outline-none focus:border-primary-500"
              min={0}
              step="0.5"
              type="number"
              {...form.register("daily_provider_budget_usd", {
                valueAsNumber: true,
              })}
            />
          </FormField>
          <FormField label="AI 日预算（USD）">
            <input
              className="h-11 w-full rounded-lg border border-border px-3 text-sm outline-none focus:border-primary-500"
              min={0}
              step="0.5"
              type="number"
              {...form.register("daily_ai_budget_usd", {
                valueAsNumber: true,
              })}
            />
          </FormField>
        </div>

        {create.error ? (
          <div className="mt-5 rounded-lg border border-red-100 bg-red-50 px-3.5 py-3 text-xs leading-5 text-red-700">
            {(create.error as { message?: string }).message ??
              "创建失败，请检查后端连接后重试。"}
          </div>
        ) : null}

        <button
          className="mt-6 inline-flex h-11 w-full items-center justify-center gap-2 rounded-lg bg-primary-600 text-sm font-medium text-white hover:bg-primary-700 disabled:opacity-60"
          disabled={create.isPending}
          type="submit"
        >
          {create.isPending ? (
            <LoaderCircle aria-hidden="true" className="animate-spin" size={16} />
          ) : (
            <ArrowRight aria-hidden="true" size={16} />
          )}
          创建并进入工作台
        </button>
      </form>
    </AuthShell>
  );
}

function FormField({
  label,
  error,
  children,
}: {
  label: string;
  error?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="mb-5 block">
      <span className="mb-2 block text-sm font-medium">{label}</span>
      {children}
      {error ? (
        <span className="mt-1.5 block text-xs text-danger">{error}</span>
      ) : null}
    </label>
  );
}
