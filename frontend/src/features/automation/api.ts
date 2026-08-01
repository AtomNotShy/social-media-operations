import { api, workspaceHeaders } from "@/src/api/client";
import type {
  AutomationSettings,
  AutomationToday,
} from "@/src/features/automation/types";

const emptyThresholds = {
  views: 0,
  likes: 0,
  comments: 0,
  favorites: 0,
  shares: 0,
};

export async function getAutomationSettings(
  workspaceId: string,
): Promise<AutomationSettings> {
  const { data } = await api.GET("/api/v1/automation/settings", {
    headers: workspaceHeaders(workspaceId),
  });
  return {
    ...data!.data,
    metric_thresholds: data!.data.metric_thresholds ?? emptyThresholds,
  };
}

export async function updateAutomationSettings(
  workspaceId: string,
  input: AutomationSettings,
): Promise<AutomationSettings> {
  const { data } = await api.PATCH("/api/v1/automation/settings", {
    headers: workspaceHeaders(workspaceId),
    body: input,
  });
  return {
    ...data!.data,
    metric_thresholds: data!.data.metric_thresholds ?? emptyThresholds,
  };
}

export async function getAutomationToday(
  workspaceId: string,
): Promise<AutomationToday> {
  const { data } = await api.GET("/api/v1/automation/today", {
    headers: workspaceHeaders(workspaceId),
  });
  return data!.data;
}
