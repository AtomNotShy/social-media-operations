"use client";

import { useQueryClient } from "@tanstack/react-query";
import {
  Bell,
  BookOpenText,
  Boxes,
  CalendarDays,
  ChartNoAxesCombined,
  ChevronDown,
  ChevronsLeft,
  ChevronsRight,
  CircleUserRound,
  Command,
  FileText,
  FlaskConical,
  GalleryVerticalEnd,
  Gauge,
  House,
  Image,
  Lightbulb,
  LogIn,
  LogOut,
  Menu,
  PlusCircle,
  Radar,
  Search,
  Settings,
  Sparkles,
  Tags,
  Users,
  X,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { setAccessToken } from "@/src/api/client";
import { localDevelopmentEnabled } from "@/src/config/runtime";
import {
  useMe,
  useWorkspaces,
  useWorkspaceRole,
} from "@/src/features/identity/queries";
import { useUnifiedSearch } from "@/src/features/production/queries";
import { useWorkbenchStore } from "@/src/stores/workbench-store";

type NavItem = {
  label: string;
  href: string;
  icon: LucideIcon;
  badge?: string;
};

const navigationGroups: { label: string; items: NavItem[] }[] = [
  {
    label: "工作区",
    items: [{ label: "今日", href: "today", icon: House }],
  },
  {
    label: "账号与定位",
    items: [
      { label: "自有账号", href: "channels", icon: CircleUserRound },
      { label: "对标账号", href: "tracked-profiles", icon: Radar },
    ],
  },
  {
    label: "内容生产",
    items: [
      { label: "选题", href: "topics", icon: Lightbulb },
      { label: "内容项目", href: "content-projects", icon: FileText },
      { label: "排期", href: "schedule", icon: CalendarDays },
      { label: "复盘", href: "reviews", icon: ChartNoAxesCombined },
      { label: "运营实验", href: "experiments", icon: FlaskConical },
    ],
  },
  {
    label: "我的资料",
    items: [
      { label: "灵感库", href: "inspirations", icon: Sparkles },
      { label: "搜索与热榜", href: "discover", icon: Search },
      { label: "素材库", href: "assets", icon: Image },
      { label: "可复用模式", href: "patterns", icon: Tags },
    ],
  },
  {
    label: "系统",
    items: [
      { label: "任务中心", href: "jobs", icon: Gauge },
      { label: "用量与费用", href: "usage", icon: Boxes },
      { label: "设置", href: "settings", icon: Settings },
    ],
  },
];

const routeTitles: Record<string, string> = Object.fromEntries(
  navigationGroups.flatMap((group) =>
    group.items.map((item) => [item.href, item.label]),
  ),
);

export function WorkbenchShell({
  children,
  workspaceId,
}: {
  children: React.ReactNode;
  workspaceId: string;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const queryClient = useQueryClient();
  const [commandOpen, setCommandOpen] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [workspaceOpen, setWorkspaceOpen] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const [commandQuery, setCommandQuery] = useState("");
  const userMenuRef = useRef<HTMLDivElement>(null);
  const collapsed = useWorkbenchStore((state) => state.collapsed);
  const toggleCollapsed = useWorkbenchStore((state) => state.toggleCollapsed);
  const tabs = useWorkbenchStore((state) => state.tabs);
  const visit = useWorkbenchStore((state) => state.visit);
  const close = useWorkbenchStore((state) => state.close);

  const segments = pathname.split("/");
  const currentSection = segments[3] ?? "today";
  const isProfileDetail =
    currentSection === "tracked-profiles" && Boolean(segments[4]);
  const currentTitle = isProfileDetail
    ? "账号详情"
    : (routeTitles[currentSection] ?? "工作台");
  const workspaces = useWorkspaces(workspaceId !== "demo");
  const identity = useMe(workspaceId !== "demo");
  const permission = useWorkspaceRole(workspaceId);
  const entitySearch = useUnifiedSearch(workspaceId, commandQuery);
  const currentWorkspace = workspaces.data?.find(
    (workspace) => workspace.id === workspaceId,
  );
  const workspaceAccessPending =
    workspaceId !== "demo" &&
    (workspaces.isPending ||
      (workspaces.isSuccess && currentWorkspace === undefined));
  const workspaceName =
    workspaceId === "demo"
      ? "增长实验室"
      : (currentWorkspace?.name ?? "当前工作区");
  const userDisplayName =
    workspaceId === "demo"
      ? "演示用户"
      : (identity.data?.user.display_name ?? "当前用户");
  const userDescription =
    workspaceId === "demo"
      ? "当前使用契约演示数据"
      : (identity.data?.user.email ??
        identity.data?.user.external_subject ??
        "本地开发身份");
  const avatarInitial = Array.from(userDisplayName.trim())[0] ?? "用";
  const workspaceTabs = useMemo(
    () => tabs.filter((tab) => tab.workspaceId === workspaceId),
    [tabs, workspaceId],
  );

  useEffect(() => {
    visit({
      key: `${workspaceId}:${pathname}`,
      workspaceId,
      href: pathname,
      title: currentTitle,
      pinned: ["today", "inspirations"].includes(currentSection),
    });
  }, [currentSection, currentTitle, pathname, visit, workspaceId]);

  useEffect(() => {
    if (
      workspaceId === "demo" ||
      workspaces.isPending ||
      workspaces.isError ||
      !workspaces.data ||
      currentWorkspace
    ) {
      return;
    }
    const fallbackWorkspace = workspaces.data[0];
    router.replace(
      fallbackWorkspace
        ? `/w/${fallbackWorkspace.id}/today`
        : "/workspaces/new",
    );
  }, [
    currentWorkspace,
    router,
    workspaceId,
    workspaces.data,
    workspaces.isError,
    workspaces.isPending,
  ]);

  useEffect(() => {
    if (!userMenuOpen) return;
    const closeOnOutsideClick = (event: PointerEvent) => {
      if (
        userMenuRef.current &&
        !userMenuRef.current.contains(event.target as Node)
      ) {
        setUserMenuOpen(false);
      }
    };
    document.addEventListener("pointerdown", closeOnOutsideClick);
    return () =>
      document.removeEventListener("pointerdown", closeOnOutsideClick);
  }, [userMenuOpen]);

  useEffect(() => {
    let prefix = "";
    const handler = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setUserMenuOpen(false);
        setCommandOpen((open) => !open);
      }
      if (event.key === "Escape") {
        setCommandOpen(false);
        setUserMenuOpen(false);
      }
      const target = event.target as HTMLElement | null;
      if (target?.matches("input, textarea, select, [contenteditable='true']")) return;
      const key = event.key.toLowerCase();
      if (key === "g") {
        prefix = "g";
        window.setTimeout(() => {
          prefix = "";
        }, 900);
        return;
      }
      if (prefix === "g") {
        const route = { t: "today", o: "topics", p: "content-projects", s: "schedule", r: "reviews" }[key];
        prefix = "";
        if (route) {
          event.preventDefault();
          router.push(`/w/${workspaceId}/${route}`);
        }
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [router, workspaceId]);

  const sidebar = (
    <aside
      className={`flex h-full flex-col border-r border-border bg-surface/95 backdrop-blur-xl transition-[width] duration-200 ${
        collapsed ? "w-[72px]" : "w-[252px]"
      }`}
    >
      <div className="flex h-[68px] items-center gap-3 border-b border-border px-4">
        <span className="grid size-9 shrink-0 place-items-center rounded-xl bg-text text-white shadow-sm">
          <GalleryVerticalEnd aria-hidden="true" size={18} />
        </span>
        {!collapsed ? (
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold tracking-tight">Xuzhang</p>
            <p className="truncate text-[11px] text-text-muted">SOCIAL CONTENT OPS</p>
          </div>
        ) : null}
      </div>

      <div className="relative p-3">
        <button
          aria-expanded={workspaceOpen}
          aria-label="切换工作区"
          className={`flex w-full items-center rounded-xl border border-border bg-surface-subtle p-2.5 text-left ${
            collapsed ? "justify-center" : "gap-3"
          }`}
          onClick={() => setWorkspaceOpen((open) => !open)}
          type="button"
        >
          <span className="grid size-7 shrink-0 place-items-center rounded-lg bg-primary-600 text-xs font-semibold text-white">
            增
          </span>
          {!collapsed ? (
            <>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm font-medium">{workspaceName}</span>
                <span className="block truncate text-[11px] text-text-muted">
                  {workspaceId === "demo"
                    ? "演示工作区"
                    : permission.role
                      ? roleLabel(permission.role)
                      : "正在验证权限"}
                </span>
              </span>
              <ChevronDown aria-hidden="true" className="text-text-muted" size={14} />
            </>
          ) : null}
        </button>
        {workspaceOpen && !collapsed ? (
          <div className="absolute left-3 right-3 top-[64px] z-40 overflow-hidden rounded-xl border border-border bg-surface p-1.5 shadow-popover">
            <p className="px-2.5 py-2 text-[10px] font-semibold tracking-[0.14em] text-text-muted uppercase">
              切换工作区
            </p>
            {workspaceId === "demo" ? (
              <div className="rounded-lg bg-primary-50 px-2.5 py-2 text-xs font-medium text-primary-700">
                增长实验室 · 演示
              </div>
            ) : workspaces.isLoading ? (
              <p className="px-2.5 py-2 text-xs text-text-muted">正在加载…</p>
            ) : (
              workspaces.data?.map((workspace) => (
                <button
                  className={`flex w-full items-center rounded-lg px-2.5 py-2 text-left text-xs ${
                    workspace.id === workspaceId
                      ? "bg-primary-50 font-medium text-primary-700"
                      : "hover:bg-surface-subtle"
                  }`}
                  key={workspace.id}
                  onClick={() => {
                    setWorkspaceOpen(false);
                    router.push(`/w/${workspace.id}/today`);
                  }}
                  type="button"
                >
                  <span className="min-w-0 flex-1 truncate">{workspace.name}</span>
                  {workspace.id === workspaceId ? "当前" : null}
                </button>
              ))
            )}
            <div className="my-1 h-px bg-border" />
            {workspaceId !== "demo" || localDevelopmentEnabled ? (
              <button
                className="flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left text-xs text-text-muted hover:bg-surface-subtle hover:text-text"
                onClick={() => router.push("/workspaces/new")}
                type="button"
              >
                <PlusCircle aria-hidden="true" size={14} />
                创建工作区
              </button>
            ) : null}
            {localDevelopmentEnabled ? (
              <button
                className="flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left text-xs text-text-muted hover:bg-surface-subtle hover:text-text"
                onClick={() => router.push("/login")}
                type="button"
              >
                <LogIn aria-hidden="true" size={14} />
                连接开发后端
              </button>
            ) : null}
          </div>
        ) : null}
      </div>

      <nav
        aria-label="工作区导航"
        className="scrollbar-subtle flex-1 overflow-y-auto px-3 pb-4"
      >
        {navigationGroups.map((group) => (
          <div className="mb-3" key={group.label}>
            {!collapsed ? (
              <p className="mb-1 px-3 pt-2 text-[10px] font-semibold tracking-[0.14em] text-text-muted/80 uppercase">
                {group.label}
              </p>
            ) : (
              <div className="mx-auto my-2 h-px w-7 bg-border" />
            )}
            <div className="space-y-0.5">
              {group.items.map((item) => {
                const href = `/w/${workspaceId}/${item.href}`;
                const active = pathname === href || pathname.startsWith(`${href}/`);
                return (
                  <Link
                    aria-label={collapsed ? item.label : undefined}
                    className={`group flex min-h-10 items-center rounded-lg text-sm transition-colors ${
                      collapsed ? "justify-center px-2" : "gap-3 px-3"
                    } ${
                      active
                        ? "bg-primary-50 font-medium text-primary-700"
                        : "text-text-muted hover:bg-surface-subtle hover:text-text"
                    }`}
                    href={href}
                    key={item.href}
                    onClick={() => setMobileOpen(false)}
                    title={collapsed ? item.label : undefined}
                  >
                    <item.icon
                      aria-hidden="true"
                      className="shrink-0"
                      size={17}
                      strokeWidth={active ? 2.2 : 1.8}
                    />
                    {!collapsed ? (
                      <>
                        <span className="flex-1">{item.label}</span>
                        {item.badge ? (
                          <span className="rounded-full bg-red-50 px-1.5 py-0.5 text-[10px] font-semibold text-red-700">
                            {item.badge}
                          </span>
                        ) : null}
                      </>
                    ) : null}
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      <div className="border-t border-border p-3">
        {!collapsed ? (
          <div className="mb-2 flex items-center gap-2 rounded-lg px-3 py-2 text-[11px] text-text-muted">
            <span
              className={`size-2 rounded-full ${
                workspaceId === "demo"
                  ? "bg-primary-500"
                  : identity.isSuccess
                    ? "bg-success"
                    : identity.isError
                      ? "bg-danger"
                      : "animate-pulse bg-warning"
              }`}
            />
            <span className="truncate">
              {workspaceId === "demo"
                ? "演示数据已就绪"
                : identity.isSuccess
                  ? "后端连接正常"
                  : identity.isError
                    ? "后端连接失败"
                    : "正在连接后端"}
            </span>
          </div>
        ) : null}
        <button
          aria-label={collapsed ? "展开侧边栏" : "收起侧边栏"}
          className="flex min-h-10 w-full items-center justify-center gap-2 rounded-lg text-sm text-text-muted hover:bg-surface-subtle hover:text-text"
          onClick={toggleCollapsed}
          type="button"
        >
          {collapsed ? (
            <ChevronsRight aria-hidden="true" size={17} />
          ) : (
            <>
              <ChevronsLeft aria-hidden="true" size={17} />
              收起导航
            </>
          )}
        </button>
      </div>
    </aside>
  );

  return (
    <div className="min-h-screen">
      <div className="fixed inset-y-0 left-0 z-30 hidden lg:block">{sidebar}</div>

      {mobileOpen ? (
        <div className="fixed inset-0 z-50 lg:hidden">
          <button
            aria-label="关闭导航"
            className="absolute inset-0 bg-text/30 backdrop-blur-sm"
            onClick={() => setMobileOpen(false)}
            type="button"
          />
          <div className="relative h-full w-[252px]">{sidebar}</div>
        </div>
      ) : null}

      <div
        className={`transition-[padding] duration-200 ${
          collapsed ? "lg:pl-[72px]" : "lg:pl-[252px]"
        }`}
      >
        <header className="sticky top-0 z-20 border-b border-border bg-canvas/92 backdrop-blur-xl">
          <div className="flex h-[50px] items-center">
            <button
              aria-label="打开导航"
              className="ml-3 grid size-9 place-items-center rounded-lg text-text-muted hover:bg-surface lg:hidden"
              onClick={() => setMobileOpen(true)}
              type="button"
            >
              <Menu aria-hidden="true" size={19} />
            </button>

            <div className="scrollbar-subtle flex min-w-0 flex-1 items-end gap-1 self-stretch overflow-x-auto px-3 pt-1">
              {workspaceTabs.map((tabItem) => {
                const active = pathname === tabItem.href;
                return (
                  <div
                    className={`group flex h-[42px] min-w-28 max-w-44 shrink-0 items-center gap-2 rounded-t-lg border-x border-t px-3 text-xs ${
                      active
                        ? "border-border bg-surface font-medium text-text"
                        : "border-transparent text-text-muted hover:bg-surface/60"
                    }`}
                    key={tabItem.key}
                  >
                    <Link className="min-w-0 flex-1 truncate" href={tabItem.href}>
                      {tabItem.title}
                    </Link>
                    {!tabItem.pinned ? (
                      <button
                        aria-label={`关闭${tabItem.title}`}
                        className="grid size-5 place-items-center rounded opacity-0 hover:bg-surface-subtle group-hover:opacity-100"
                        onClick={() => close(tabItem.key)}
                        type="button"
                      >
                        <X aria-hidden="true" size={12} />
                      </button>
                    ) : null}
                  </div>
                );
              })}
            </div>

            <div className="flex shrink-0 items-center gap-1 px-3">
              <button
                aria-label="打开命令面板"
                className="hidden items-center gap-2 rounded-lg border border-border bg-surface px-3 py-1.5 text-xs text-text-muted shadow-panel sm:flex"
                onClick={() => {
                  setUserMenuOpen(false);
                  setCommandOpen(true);
                }}
                type="button"
              >
                <Search aria-hidden="true" size={14} />
                搜索或跳转
                <kbd className="rounded border border-border bg-surface-subtle px-1.5 py-0.5 font-sans text-[10px]">
                  ⌘K
                </kbd>
              </button>
              <Link
                aria-label="任务中心"
                className="relative grid size-9 place-items-center rounded-lg text-text-muted hover:bg-surface"
                href={`/w/${workspaceId}/jobs`}
              >
                <Bell aria-hidden="true" size={18} />
              </Link>
              <div className="relative ml-1" ref={userMenuRef}>
                <button
                  aria-expanded={userMenuOpen}
                  aria-haspopup="menu"
                  aria-label="用户菜单"
                  className={`grid size-8 place-items-center rounded-full bg-text text-xs font-semibold text-white outline-none transition-shadow hover:ring-4 hover:ring-primary-100 focus-visible:ring-4 focus-visible:ring-primary-200 ${
                    userMenuOpen ? "ring-4 ring-primary-100" : ""
                  }`}
                  onClick={() => setUserMenuOpen((open) => !open)}
                  type="button"
                >
                  {avatarInitial}
                </button>

                {userMenuOpen ? (
                  <div
                    aria-label="账户菜单"
                    className="absolute top-11 right-0 z-50 w-64 overflow-hidden rounded-xl border border-border bg-surface shadow-popover"
                    role="menu"
                  >
                    <div className="border-b border-border px-4 py-3">
                      <p className="truncate text-sm font-semibold">
                        {userDisplayName}
                      </p>
                      <p className="mt-0.5 truncate text-xs text-text-muted">
                        {userDescription}
                      </p>
                      <span className="mt-2 inline-flex rounded-full bg-primary-50 px-2 py-0.5 text-[10px] font-semibold text-primary-700">
                        {permission.role
                          ? roleLabel(permission.role)
                          : "正在验证权限"}
                      </span>
                    </div>
                    <div className="p-1.5">
                      <button
                        className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-xs text-text-muted hover:bg-surface-subtle hover:text-text"
                        onClick={() => {
                          setUserMenuOpen(false);
                          router.push(`/w/${workspaceId}/settings`);
                        }}
                        role="menuitem"
                        type="button"
                      >
                        <Settings aria-hidden="true" size={15} />
                        工作区设置
                      </button>
                      {workspaceId === "demo" &&
                      localDevelopmentEnabled ? (
                        <button
                          className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-xs text-text-muted hover:bg-surface-subtle hover:text-text"
                          onClick={() => {
                            setUserMenuOpen(false);
                            router.push("/login");
                          }}
                          role="menuitem"
                          type="button"
                        >
                          <LogIn aria-hidden="true" size={15} />
                          连接真实后端
                        </button>
                      ) : workspaceId !== "demo" ? (
                        <button
                          className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-xs text-danger hover:bg-red-50"
                          onClick={() => {
                            setAccessToken(null);
                            queryClient.clear();
                            setUserMenuOpen(false);
                            router.push("/login");
                          }}
                          role="menuitem"
                          type="button"
                        >
                          <LogOut aria-hidden="true" size={15} />
                          退出当前身份
                        </button>
                      ) : null}
                    </div>
                  </div>
                ) : null}
              </div>
            </div>
          </div>
        </header>

        <main className="mx-auto max-w-[1680px] px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
          {workspaceId === "demo" ? (
            <div className="mb-4 flex items-center justify-between gap-3 rounded-lg border border-primary-100 bg-primary-50 px-3.5 py-2 text-xs text-primary-700">
              <span>
                当前展示契约演示数据；页面操作只影响演示状态，不会写入真实工作区。
              </span>
              <span className="hidden rounded-full bg-white/70 px-2 py-1 font-semibold sm:inline">
                DEMO
              </span>
            </div>
          ) : null}
          {workspaceAccessPending ? (
            <div
              aria-live="polite"
              className="flex min-h-64 items-center justify-center text-sm text-text-muted"
            >
              正在验证工作区权限…
            </div>
          ) : (
            children
          )}
        </main>
      </div>

      {commandOpen ? (
        <div
          aria-label="命令面板"
          aria-modal="true"
          className="fixed inset-0 z-[60] flex items-start justify-center bg-text/30 px-4 pt-[12vh] backdrop-blur-sm"
          role="dialog"
        >
          <button
            aria-label="关闭命令面板"
            className="absolute inset-0"
            onClick={() => setCommandOpen(false)}
            type="button"
          />
          <div className="relative w-full max-w-2xl overflow-hidden rounded-2xl border border-border bg-surface shadow-popover">
            <div className="flex items-center gap-3 border-b border-border px-4">
              <Command aria-hidden="true" className="text-text-muted" size={18} />
              <input
                aria-label="搜索命令"
                autoFocus
                className="h-14 flex-1 border-0 bg-transparent text-sm outline-none placeholder:text-text-muted"
                onChange={(event) => setCommandQuery(event.target.value)}
                placeholder="搜索灵感、模式、选题、项目或输入命令…"
                value={commandQuery}
              />
              <kbd className="rounded border border-border bg-surface-subtle px-2 py-1 text-[10px] text-text-muted">
                ESC
              </kbd>
            </div>
            <div className="max-h-[58vh] overflow-y-auto p-2">
              {commandQuery.trim().length >= 2 ? (
                <>
                  <div className="flex items-center justify-between px-3 py-2">
                    <p className="text-[10px] font-semibold tracking-[0.14em] text-text-muted uppercase">
                      工作区结果
                    </p>
                    <span className="text-[10px] text-text-muted">
                      可解释关键词匹配
                    </span>
                  </div>
                  {entitySearch.isLoading ? (
                    <p className="px-3 py-4 text-xs text-text-muted">正在搜索…</p>
                  ) : entitySearch.data?.length ? (
                    entitySearch.data.map((result) => (
                      <button
                        className="flex w-full items-start gap-3 rounded-lg px-3 py-2.5 text-left hover:bg-surface-subtle"
                        key={`${result.entity_type}:${result.entity_id}`}
                        onClick={() => {
                          const route =
                            result.entity_type === "content_project"
                              ? `content-projects/${result.entity_id}`
                              : result.entity_type === "topic"
                                ? `topics/${result.entity_id}`
                                : result.entity_type === "inspiration"
                                  ? `inspirations/${result.entity_id}`
                                  : `patterns/${result.entity_id}`;
                          setCommandOpen(false);
                          setCommandQuery("");
                          router.push(`/w/${workspaceId}/${route}`);
                        }}
                        type="button"
                      >
                        <Search className="mt-0.5 shrink-0 text-primary-600" size={15} />
                        <span className="min-w-0">
                          <strong className="block truncate text-sm">{result.title}</strong>
                          <span className="mt-0.5 block truncate text-xs text-text-muted">
                            {result.entity_type} · {result.snippet || result.matched_fields.join("、")}
                          </span>
                        </span>
                      </button>
                    ))
                  ) : (
                    <p className="px-3 py-4 text-xs text-text-muted">
                      没有匹配的工作区实体。
                    </p>
                  )}
                  <div className="my-2 h-px bg-border" />
                </>
              ) : null}
              <p className="px-3 py-2 text-[10px] font-semibold tracking-[0.14em] text-text-muted uppercase">
                快速前往
              </p>
              {[
                { icon: Radar, label: "打开对标账号", href: "tracked-profiles" },
                { icon: Gauge, label: "打开任务中心", href: "jobs" },
                { icon: BookOpenText, label: "打开灵感库", href: "inspirations" },
                { icon: Search, label: "打开搜索与热榜", href: "discover" },
                { icon: Tags, label: "打开可复用模式", href: "patterns" },
                { icon: Lightbulb, label: "打开选题", href: "topics" },
                { icon: FileText, label: "打开内容项目", href: "content-projects" },
                { icon: CalendarDays, label: "打开内容排期", href: "schedule" },
                { icon: FlaskConical, label: "打开运营实验", href: "experiments" },
                { icon: Boxes, label: "打开用量与费用", href: "usage" },
                ...(permission.canEdit
                  ? [
                      {
                        icon: Users,
                        label: "新建对标账号",
                        href: "tracked-profiles?create=1",
                      },
                      {
                        icon: Sparkles,
                        label: "导入内容链接",
                        href: "inspirations?import=1",
                      },
                      {
                        icon: Lightbulb,
                        label: "新建选题",
                        href: "topics?create=1",
                      },
                    ]
                  : []),
              ].map((item) => (
                <button
                  className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm hover:bg-surface-subtle"
                  key={item.label}
                  onClick={() => {
                    setCommandOpen(false);
                    router.push(`/w/${workspaceId}/${item.href}`);
                  }}
                  type="button"
                >
                  <item.icon aria-hidden="true" className="text-text-muted" size={17} />
                  {item.label}
                </button>
              ))}
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function roleLabel(role: string) {
  return (
    {
      owner: "所有者",
      editor: "编辑者",
      viewer: "只读成员",
    }[role] ?? role
  );
}
