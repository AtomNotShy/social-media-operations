import { api, workspaceHeaders } from "@/src/api/client";

export async function getProviderUsage(
  workspaceId: string,
  dateFrom?: string,
  dateTo?: string,
) {
  const { data } = await api.GET("/api/v1/usage/provider", {
    headers: workspaceHeaders(workspaceId),
    params: { query: { date_from: dateFrom, date_to: dateTo } },
  });
  return data!.data;
}

export async function getAIUsage(
  workspaceId: string,
  dateFrom?: string,
  dateTo?: string,
) {
  const { data } = await api.GET("/api/v1/usage/ai", {
    headers: workspaceHeaders(workspaceId),
    params: { query: { date_from: dateFrom, date_to: dateTo } },
  });
  return data!.data;
}

export async function getASRUsage(
  workspaceId: string,
  dateFrom?: string,
  dateTo?: string,
) {
  const { data } = await api.GET("/api/v1/usage/asr", {
    headers: workspaceHeaders(workspaceId),
    params: { query: { date_from: dateFrom, date_to: dateTo } },
  });
  return data!.data;
}
