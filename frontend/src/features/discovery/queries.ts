"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { queryKeys } from "@/src/api/query-keys";
import {
  createDiscoverySearch,
  getDiscoverySearchEstimate,
  getDiscoverySearch,
  importDiscoveryResults,
} from "@/src/features/discovery/api";
import type {
  DiscoverySearch,
  DiscoverySearchRequest,
} from "@/src/features/discovery/types";
import { demoDiscoverySearch } from "@/src/test/fixtures";

export function useDiscoverySearchEstimate(
  workspaceId: string,
  maxPages: number,
) {
  return useQuery({
    queryKey: queryKeys.discovery.estimate(workspaceId, maxPages),
    queryFn: () =>
      workspaceId === "demo"
        ? {
            provider_calls: maxPages,
            estimated_provider_cost_usd: (maxPages * 0.001).toFixed(3),
          }
        : getDiscoverySearchEstimate(workspaceId, maxPages),
    staleTime: 5 * 60_000,
  });
}

export function useCreateDiscoverySearch(workspaceId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (input: DiscoverySearchRequest) => {
      if (workspaceId !== "demo") {
        return createDiscoverySearch(workspaceId, input);
      }
      return {
        search_id: demoDiscoverySearch.id,
        job_id: demoDiscoverySearch.sync_job_id!,
        status: "pending",
        estimated_provider_cost_usd: "0.0500",
      };
    },
    onSuccess: (accepted) => {
      if (workspaceId === "demo") {
        client.setQueryData<DiscoverySearch>(
          queryKeys.discovery.search(workspaceId, accepted.job_id),
          structuredClone(demoDiscoverySearch),
        );
      }
      client.invalidateQueries({ queryKey: queryKeys.jobs.all(workspaceId) });
    },
  });
}

export function useDiscoverySearch(workspaceId: string, jobId?: string) {
  return useQuery({
    queryKey: queryKeys.discovery.search(workspaceId, jobId ?? "none"),
    enabled: Boolean(jobId),
    queryFn: () =>
      workspaceId === "demo"
        ? structuredClone(demoDiscoverySearch)
        : getDiscoverySearch(workspaceId, jobId!),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status && !["succeeded", "failed", "cancelled"].includes(status)
        ? 3_000
        : false;
    },
  });
}

export function useImportDiscoveryResults(
  workspaceId: string,
  jobId?: string,
) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (resultIds: string[]) => {
      if (!jobId) throw new Error("搜索任务不存在。");
      if (workspaceId !== "demo") {
        return importDiscoveryResults(workspaceId, jobId, resultIds);
      }
      return {
        inspiration_ids: resultIds.map((_, index) =>
          `a11d18b5-aeb6-4fc1-a146-1c1cd843b${String(index).padStart(3, "0")}`,
        ),
        hydration_job_ids: resultIds.map(() => crypto.randomUUID()),
      };
    },
    onSuccess: () => {
      client.invalidateQueries({
        queryKey: queryKeys.inspirations.all(workspaceId),
      });
      client.invalidateQueries({ queryKey: queryKeys.jobs.all(workspaceId) });
      client.invalidateQueries({
        queryKey: queryKeys.discovery.search(workspaceId, jobId ?? "none"),
      });
    },
  });
}
