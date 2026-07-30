"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { queryKeys } from "@/src/api/query-keys";
import { listJobs, updateJob } from "@/src/features/jobs/api";
import type { Job } from "@/src/features/tracked-profiles/types";
import { isTerminalJob } from "@/src/lib/format";
import { demoJobs } from "@/src/test/fixtures";

export function useJobs(workspaceId: string, status?: string) {
  return useQuery({
    queryKey: [...queryKeys.jobs.all(workspaceId), { status }],
    queryFn: () =>
      workspaceId === "demo"
        ? Promise.resolve(
            structuredClone(demoJobs).filter(
              (job) => !status || job.status === status,
            ),
          )
        : listJobs(workspaceId, status),
    refetchInterval: (query) => {
      const jobs = query.state.data;
      if (!jobs?.some((job) => !isTerminalJob(job.status))) return false;
      if (document.visibilityState === "hidden") return 15_000;
      return jobs.some((job) => job.status === "running") ? 2_000 : 5_000;
    },
  });
}

export function useJobAction(workspaceId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async ({
      job,
      action,
    }: {
      job: Job;
      action: "retry" | "cancel";
    }) => {
      if (workspaceId !== "demo") return updateJob(workspaceId, job, action);
      return {
        ...job,
        status: action === "retry" ? "pending" : "cancelled",
        finished_at:
          action === "cancel" ? new Date().toISOString() : null,
        run_after: new Date().toISOString(),
      } satisfies Job;
    },
    onSuccess: (updated) => {
      client.setQueriesData<Job[]>(
        { queryKey: queryKeys.jobs.all(workspaceId) },
        (current) =>
          current?.map((job) => (job.id === updated.id ? updated : job)),
      );
    },
  });
}
