"use client";

import { useQueryClient } from "@tanstack/react-query";
import { ArrowRight, FlaskConical, LoaderCircle } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { setAccessToken } from "@/src/api/client";
import { queryKeys } from "@/src/api/query-keys";
import { AuthShell } from "@/src/features/identity/auth-shell";
import { getMe, listWorkspaces } from "@/src/features/identity/api";

export function DevLoginPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [subject, setSubject] = useState("local-owner");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string>();

  async function connect(event: React.FormEvent) {
    event.preventDefault();
    const normalized = subject.trim();
    if (!normalized) {
      setError("请输入开发身份标识。");
      return;
    }
    setPending(true);
    setError(undefined);
    setAccessToken(`dev:${normalized}`);
    queryClient.clear();
    try {
      const [me, workspaces] = await Promise.all([getMe(), listWorkspaces()]);
      queryClient.setQueryData(queryKeys.me, me);
      queryClient.setQueryData(queryKeys.workspaces, workspaces);
      router.push(
        workspaces.length
          ? `/w/${workspaces[0].id}/today`
          : "/workspaces/new",
      );
    } catch (caught) {
      setError(
        (caught as { message?: string }).message ??
          "无法连接后端，请确认服务已启动并允许当前前端地址访问。",
      );
    } finally {
      setPending(false);
    }
  }

  return (
    <AuthShell
      description="仅供本地开发：使用后端 development 模式建立调试身份，读取本机工作区、成员角色和业务数据。"
      eyebrow="Local development"
      title="连接开发后端"
    >
      <div className="rounded-2xl border border-border bg-surface p-6 shadow-panel sm:p-8">
        <div className="mb-6 flex items-start gap-3 rounded-xl border border-amber-100 bg-amber-50 p-3.5 text-amber-800">
          <FlaskConical aria-hidden="true" className="mt-0.5 shrink-0" size={17} />
          <p className="text-xs leading-5">
            此入口只在本地开发构建中开放，线上访问会直接返回演示工作台。
          </p>
        </div>
        <form onSubmit={connect}>
          <label className="block text-sm font-medium" htmlFor="dev-subject">
            开发身份
          </label>
          <div className="mt-2 flex h-11 items-center rounded-lg border border-border bg-surface focus-within:border-primary-500">
            <span className="border-r border-border px-3 text-xs text-text-muted">
              dev:
            </span>
            <input
              autoComplete="off"
              className="min-w-0 flex-1 bg-transparent px-3 text-sm outline-none"
              id="dev-subject"
              onChange={(event) => setSubject(event.target.value)}
              spellCheck={false}
              value={subject}
            />
          </div>
          <p className="mt-2 text-xs leading-5 text-text-muted">
            首次使用该身份时，后端会创建对应的本地用户。
          </p>

          {error ? (
            <div className="mt-4 rounded-lg border border-red-100 bg-red-50 px-3.5 py-3 text-xs leading-5 text-red-700">
              {error}
            </div>
          ) : null}

          <button
            className="mt-6 inline-flex h-11 w-full items-center justify-center gap-2 rounded-lg bg-primary-600 text-sm font-medium text-white hover:bg-primary-700 disabled:opacity-60"
            disabled={pending}
            type="submit"
          >
            {pending ? (
              <LoaderCircle aria-hidden="true" className="animate-spin" size={16} />
            ) : (
              <ArrowRight aria-hidden="true" size={16} />
            )}
            连接并继续
          </button>
        </form>
        <div className="mt-5 border-t border-border pt-5 text-center">
          <Link
            className="text-xs font-medium text-primary-600 hover:text-primary-700"
            href="/w/demo/today"
          >
            暂不连接，查看演示工作区
          </Link>
        </div>
      </div>
    </AuthShell>
  );
}
