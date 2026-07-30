"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";

export type WorkbenchTab = {
  key: string;
  workspaceId: string;
  href: string;
  title: string;
  pinned?: boolean;
  lastVisitedAt: number;
};

type WorkbenchState = {
  collapsed: boolean;
  tabs: WorkbenchTab[];
  toggleCollapsed: () => void;
  visit: (tab: Omit<WorkbenchTab, "lastVisitedAt">) => void;
  close: (key: string) => void;
};

export const useWorkbenchStore = create<WorkbenchState>()(
  persist(
    (set) => ({
      collapsed: false,
      tabs: [],
      toggleCollapsed: () => set((state) => ({ collapsed: !state.collapsed })),
      visit: (tab) =>
        set((state) => {
          const existing = state.tabs.find((item) => item.key === tab.key);
          const updated = existing
            ? state.tabs.map((item) =>
                item.key === tab.key
                  ? { ...item, ...tab, lastVisitedAt: Date.now() }
                  : item,
              )
            : [...state.tabs, { ...tab, lastVisitedAt: Date.now() }];
          const workspaceTabs = updated.filter(
            (item) => item.workspaceId === tab.workspaceId,
          );
          if (workspaceTabs.length <= 12) return { tabs: updated };
          const oldest = workspaceTabs
            .filter((item) => !item.pinned && item.key !== tab.key)
            .sort((a, b) => a.lastVisitedAt - b.lastVisitedAt)[0];
          return {
            tabs: oldest
              ? updated.filter((item) => item.key !== oldest.key)
              : updated,
          };
        }),
      close: (key) =>
        set((state) => ({
          tabs: state.tabs.filter((item) => item.key !== key),
        })),
    }),
    {
      name: "social-ops-workbench",
      partialize: (state) => ({
        collapsed: state.collapsed,
        tabs: state.tabs,
      }),
    },
  ),
);
