import { api, workspaceHeaders } from "@/src/api/client";
import type { DiscoverySearchRequest } from "@/src/features/discovery/types";

export async function createDiscoverySearch(
  workspaceId: string,
  input: DiscoverySearchRequest,
) {
  const { data } = await api.POST("/api/v1/discover/search", {
    headers: {
      ...workspaceHeaders(workspaceId),
      "Idempotency-Key": crypto.randomUUID(),
    },
    body: input,
  });
  return data!.data;
}

export async function getDiscoverySearchEstimate(
  workspaceId: string,
  maxPages: number,
) {
  const { data } = await api.GET("/api/v1/discover/search-estimate", {
    headers: workspaceHeaders(workspaceId),
    params: { query: { max_pages: maxPages } },
  });
  return data!.data;
}

export async function getDiscoverySearch(
  workspaceId: string,
  jobId: string,
) {
  const { data } = await api.GET(
    "/api/v1/discover/search-jobs/{job_id}",
    {
      headers: workspaceHeaders(workspaceId),
      params: { path: { job_id: jobId } },
    },
  );
  return data!.data;
}

export async function importDiscoveryResults(
  workspaceId: string,
  jobId: string,
  resultIds: string[],
) {
  const { data } = await api.POST(
    "/api/v1/discover/search-jobs/{job_id}/import",
    {
      headers: workspaceHeaders(workspaceId),
      params: { path: { job_id: jobId } },
      body: { result_ids: resultIds, hydrate: true },
    },
  );
  return data!.data;
}
