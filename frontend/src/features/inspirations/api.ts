import { api, workspaceHeaders } from "@/src/api/client";
import type { InspirationFilters } from "@/src/api/query-keys";
import type {
  ImportURLRequest,
  InspirationUpdate,
  TopicFromInspiration,
} from "@/src/features/inspirations/types";

export async function listInspirations(
  workspaceId: string,
  filters: InspirationFilters,
) {
  const { data } = await api.GET("/api/v1/inspirations", {
    headers: workspaceHeaders(workspaceId),
    params: {
      query: {
        platform: filters.platform,
        status: filters.status,
        query: filters.q,
        limit: 100,
      },
    },
  });
  return data?.data ?? [];
}

export async function getInspiration(
  workspaceId: string,
  inspirationId: string,
) {
  const { data } = await api.GET(
    "/api/v1/inspirations/{inspiration_id}",
    {
      headers: workspaceHeaders(workspaceId),
      params: { path: { inspiration_id: inspirationId } },
    },
  );
  return data!.data;
}

export async function importInspirationURL(
  workspaceId: string,
  input: ImportURLRequest,
) {
  const { data } = await api.POST("/api/v1/inspirations/import-url", {
    headers: {
      ...workspaceHeaders(workspaceId),
      "Idempotency-Key": crypto.randomUUID(),
    },
    body: input,
  });
  return data!.data;
}

export async function updateInspiration(
  workspaceId: string,
  inspirationId: string,
  input: InspirationUpdate,
) {
  const { data } = await api.PATCH(
    "/api/v1/inspirations/{inspiration_id}",
    {
      headers: workspaceHeaders(workspaceId),
      params: { path: { inspiration_id: inspirationId } },
      body: input,
    },
  );
  return data!.data;
}

export async function setInspirationArchived(
  workspaceId: string,
  inspirationId: string,
  archived: boolean,
) {
  const path = archived
    ? "/api/v1/inspirations/{inspiration_id}/archive"
    : "/api/v1/inspirations/{inspiration_id}/restore";
  const { data } = await api.POST(path, {
    headers: workspaceHeaders(workspaceId),
    params: { path: { inspiration_id: inspirationId } },
  });
  return data!.data;
}

export async function listScores(workspaceId: string, inspirationId: string) {
  const { data } = await api.GET(
    "/api/v1/inspirations/{inspiration_id}/scores",
    {
      headers: workspaceHeaders(workspaceId),
      params: { path: { inspiration_id: inspirationId } },
    },
  );
  return data?.data ?? [];
}

export async function listMetrics(workspaceId: string, inspirationId: string) {
  const { data } = await api.GET(
    "/api/v1/inspirations/{inspiration_id}/metrics",
    {
      headers: workspaceHeaders(workspaceId),
      params: {
        path: { inspiration_id: inspirationId },
        query: { limit: 30 },
      },
    },
  );
  return data?.data ?? [];
}

export async function recalculateScore(
  workspaceId: string,
  inspirationId: string,
) {
  const { data } = await api.POST(
    "/api/v1/inspirations/{inspiration_id}/scores/recalculate",
    {
      headers: workspaceHeaders(workspaceId),
      params: { path: { inspiration_id: inspirationId } },
    },
  );
  return data!.data;
}

export async function listComments(workspaceId: string, inspirationId: string) {
  const { data } = await api.GET(
    "/api/v1/inspirations/{inspiration_id}/comments",
    {
      headers: workspaceHeaders(workspaceId),
      params: { path: { inspiration_id: inspirationId }, query: { limit: 50 } },
    },
  );
  return data?.data ?? [];
}

export async function fetchComments(
  workspaceId: string,
  inspirationId: string,
) {
  const { data } = await api.POST(
    "/api/v1/inspirations/{inspiration_id}/fetch-comments",
    {
      headers: {
        ...workspaceHeaders(workspaceId),
        "Idempotency-Key": crypto.randomUUID(),
      },
      params: { path: { inspiration_id: inspirationId } },
      body: { max_pages: 1, sort_strategy: "latest_v2" },
    },
  );
  return data!.data;
}

export async function listAnalyses(workspaceId: string, inspirationId: string) {
  const { data } = await api.GET(
    "/api/v1/inspirations/{inspiration_id}/analyses",
    {
      headers: workspaceHeaders(workspaceId),
      params: { path: { inspiration_id: inspirationId } },
    },
  );
  return data?.data ?? [];
}

export async function analyzeInspiration(
  workspaceId: string,
  inspirationId: string,
  level: "l1" | "l2",
) {
  const { data } = await api.POST(
    "/api/v1/inspirations/{inspiration_id}/analyze",
    {
      headers: {
        ...workspaceHeaders(workspaceId),
        "Idempotency-Key": crypto.randomUUID(),
      },
      params: { path: { inspiration_id: inspirationId } },
      body: { level, force: false },
    },
  );
  return data!.data;
}

export async function listTranscripts(
  workspaceId: string,
  inspirationId: string,
) {
  const { data } = await api.GET(
    "/api/v1/inspirations/{inspiration_id}/transcripts",
    {
      headers: workspaceHeaders(workspaceId),
      params: { path: { inspiration_id: inspirationId } },
    },
  );
  return data?.data ?? [];
}

export async function transcribeInspiration(
  workspaceId: string,
  inspirationId: string,
) {
  const { data } = await api.POST(
    "/api/v1/inspirations/{inspiration_id}/transcribe",
    {
      headers: {
        ...workspaceHeaders(workspaceId),
        "Idempotency-Key": crypto.randomUUID(),
      },
      params: { path: { inspiration_id: inspirationId } },
    },
  );
  return data!.data;
}

export async function listProfileContents(
  workspaceId: string,
  profileId: string,
) {
  const { data } = await api.GET(
    "/api/v1/tracked-profiles/{profile_id}/contents",
    {
      headers: workspaceHeaders(workspaceId),
      params: { path: { profile_id: profileId }, query: { limit: 12 } },
    },
  );
  return data?.data ?? [];
}

export async function createTopicFromInspiration(
  workspaceId: string,
  inspirationId: string,
  input: TopicFromInspiration,
) {
  const { data } = await api.POST(
    "/api/v1/topics/from-inspiration/{inspiration_id}",
    {
      headers: workspaceHeaders(workspaceId),
      params: { path: { inspiration_id: inspirationId } },
      body: input,
    },
  );
  return data!.data;
}
