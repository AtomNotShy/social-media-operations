import { api, workspaceHeaders } from "@/src/api/client";
import type { Job } from "@/src/features/tracked-profiles/types";

export async function listJobs(workspaceId: string, status?: string) {
  const { data } = await api.GET("/api/v1/jobs", {
    headers: workspaceHeaders(workspaceId),
    params: { query: { limit: 100, status } },
  });
  return data?.data ?? [];
}

export async function updateJob(
  workspaceId: string,
  job: Job,
  action: "retry" | "cancel",
) {
  const path =
    action === "retry"
      ? "/api/v1/jobs/{job_id}/retry"
      : "/api/v1/jobs/{job_id}/cancel";
  const { data } = await api.POST(path, {
    headers: workspaceHeaders(workspaceId),
    params: { path: { job_id: job.id } },
  });
  return data!.data;
}
