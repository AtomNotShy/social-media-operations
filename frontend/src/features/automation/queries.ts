"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { queryKeys } from "@/src/api/query-keys";
import * as service from "@/src/features/automation/api";
import {
  demoAutomationSettings,
  demoAutomationToday,
  type AutomationSettings,
} from "@/src/features/automation/types";

function clone<T>(value: T): T {
  return structuredClone(value);
}

export function useAutomationSettings(workspaceId: string) {
  return useQuery({
    queryKey: queryKeys.settings.automation(workspaceId),
    queryFn: () =>
      workspaceId === "demo"
        ? clone(demoAutomationSettings)
        : service.getAutomationSettings(workspaceId),
  });
}

export function useUpdateAutomationSettings(workspaceId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: AutomationSettings) =>
      workspaceId === "demo"
        ? Promise.resolve(clone(input))
        : service.updateAutomationSettings(workspaceId, input),
    onSuccess: (settings) => {
      client.setQueryData(
        queryKeys.settings.automation(workspaceId),
        settings,
      );
      client.invalidateQueries({
        queryKey: queryKeys.production.automationToday(workspaceId),
      });
    },
  });
}

export function useAutomationToday(workspaceId: string) {
  return useQuery({
    queryKey: queryKeys.production.automationToday(workspaceId),
    queryFn: () =>
      workspaceId === "demo"
        ? clone(demoAutomationToday)
        : service.getAutomationToday(workspaceId),
    refetchInterval: 60_000,
  });
}
