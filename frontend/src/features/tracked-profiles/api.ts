import { api, workspaceHeaders } from "@/src/api/client";
import type {
  Job,
  TrackedProfile,
  TrackedProfileCreate,
  TrackedProfileOverview,
  TrackedProfileUpdate,
} from "@/src/features/tracked-profiles/types";

export async function listTrackedProfiles(
  workspaceId: string,
  active?: boolean,
) {
  const { data } = await api.GET("/api/v1/tracked-profiles", {
    headers: workspaceHeaders(workspaceId),
    params: { query: { active, limit: 100 } },
  });
  return data?.data ?? [];
}

export async function createTrackedProfile(
  workspaceId: string,
  input: TrackedProfileCreate,
) {
  const { data } = await api.POST("/api/v1/tracked-profiles", {
    headers: workspaceHeaders(workspaceId),
    body: input,
  });
  return data!.data;
}

export async function getTrackedProfile(
  workspaceId: string,
  profileId: string,
) {
  const { data } = await api.GET(
    "/api/v1/tracked-profiles/{profile_id}",
    {
      headers: workspaceHeaders(workspaceId),
      params: { path: { profile_id: profileId } },
    },
  );
  return data!.data;
}

export async function getTrackedProfileOverview(
  workspaceId: string,
  profileId: string,
  windowDays = 30,
  limit = 12,
): Promise<TrackedProfileOverview> {
  const { data } = await api.GET(
    "/api/v1/tracked-profiles/{profile_id}/overview",
    {
      headers: workspaceHeaders(workspaceId),
      params: {
        path: { profile_id: profileId },
        query: { window_days: windowDays, limit },
      },
    },
  );
  return data!.data;
}

export async function updateTrackedProfile(
  workspaceId: string,
  profileId: string,
  input: TrackedProfileUpdate,
) {
  const { data } = await api.PATCH(
    "/api/v1/tracked-profiles/{profile_id}",
    {
      headers: workspaceHeaders(workspaceId),
      params: { path: { profile_id: profileId } },
      body: input,
    },
  );
  return data!.data;
}

export async function deleteTrackedProfile(
  workspaceId: string,
  profileId: string,
) {
  await api.DELETE("/api/v1/tracked-profiles/{profile_id}", {
    headers: workspaceHeaders(workspaceId),
    params: { path: { profile_id: profileId } },
  });
}

export async function changeTrackedProfileStatus(
  workspaceId: string,
  profile: TrackedProfile,
) {
  const path = profile.active
    ? "/api/v1/tracked-profiles/{profile_id}/pause"
    : "/api/v1/tracked-profiles/{profile_id}/resume";
  const { data } = await api.POST(path, {
    headers: workspaceHeaders(workspaceId),
    params: { path: { profile_id: profile.id } },
  });
  return data!.data;
}

export async function syncTrackedProfile(
  workspaceId: string,
  profileId: string,
): Promise<Pick<Job, "id" | "status">> {
  const { data } = await api.POST(
    "/api/v1/tracked-profiles/{profile_id}/sync",
    {
      headers: {
        ...workspaceHeaders(workspaceId),
        "Idempotency-Key": crypto.randomUUID(),
      },
      params: { path: { profile_id: profileId } },
    },
  );
  return { id: data!.data.job_id, status: data!.data.status };
}
