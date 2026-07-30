"use client";

import { useQuery } from "@tanstack/react-query";
import { queryKeys } from "@/src/api/query-keys";
import {
  getAIUsage,
  getASRUsage,
  getProviderUsage,
} from "@/src/features/usage/api";
import { demoProviderUsage } from "@/src/test/fixtures";

export function useProviderUsage(
  workspaceId: string,
  dateFrom?: string,
  dateTo?: string,
) {
  return useQuery({
    queryKey: queryKeys.usage.provider(workspaceId, dateFrom, dateTo),
    queryFn: () =>
      workspaceId === "demo"
        ? structuredClone(demoProviderUsage)
        : getProviderUsage(workspaceId, dateFrom, dateTo),
    staleTime: 30_000,
  });
}

export function useAIUsage(
  workspaceId: string,
  dateFrom?: string,
  dateTo?: string,
) {
  return useQuery({
    queryKey: queryKeys.usage.ai(workspaceId, dateFrom, dateTo),
    queryFn: () =>
      workspaceId === "demo"
        ? {
            run_count: 18,
            success_count: 17,
            input_tokens: 28_400,
            output_tokens: 9_860,
            cost_usd: "0.8420",
          }
        : getAIUsage(workspaceId, dateFrom, dateTo),
    staleTime: 30_000,
  });
}

export function useASRUsage(
  workspaceId: string,
  dateFrom?: string,
  dateTo?: string,
) {
  return useQuery({
    queryKey: queryKeys.usage.asr(workspaceId, dateFrom, dateTo),
    queryFn: () =>
      workspaceId === "demo"
        ? {
            transcript_count: 7,
            success_count: 7,
            audio_duration_ms: 1_284_000,
            cost_usd: "0.2160",
          }
        : getASRUsage(workspaceId, dateFrom, dateTo),
    staleTime: 30_000,
  });
}
