import { api, workspaceHeaders } from "@/src/api/client";
import type {
  ContentProjectCreate,
  ContentProjectUpdate,
  ExperimentCreate,
  MarkPublished,
  OwnedChannelCreate,
  PositioningUpdate,
  PublishPlanCreate,
  PublishPlanUpdate,
  ReviewCreate,
  SavedViewCreate,
  ScriptCreate,
  TopicCreate,
  TopicUpdate,
} from "@/src/features/production/types";

export async function listChannels(workspaceId: string) {
  const { data } = await api.GET("/api/v1/owned-channels", {
    headers: workspaceHeaders(workspaceId),
  });
  return data?.data ?? [];
}

export async function getChannel(workspaceId: string, channelId: string) {
  const { data } = await api.GET("/api/v1/owned-channels/{channel_id}", {
    headers: workspaceHeaders(workspaceId),
    params: { path: { channel_id: channelId } },
  });
  return data!.data;
}

export async function createChannel(
  workspaceId: string,
  input: OwnedChannelCreate,
) {
  const { data } = await api.POST("/api/v1/owned-channels", {
    headers: workspaceHeaders(workspaceId),
    body: input,
  });
  return data!.data;
}

export async function savePositioning(
  workspaceId: string,
  channelId: string,
  input: PositioningUpdate,
) {
  const { data } = await api.PUT(
    "/api/v1/owned-channels/{channel_id}/positioning",
    {
      headers: workspaceHeaders(workspaceId),
      params: { path: { channel_id: channelId } },
      body: input,
    },
  );
  return data!.data;
}

export async function listTopics(workspaceId: string, status?: string) {
  const { data } = await api.GET("/api/v1/topics", {
    headers: workspaceHeaders(workspaceId),
    params: { query: { status_filter: status } },
  });
  return data?.data ?? [];
}

export async function getTopic(workspaceId: string, topicId: string) {
  const { data } = await api.GET("/api/v1/topics/{topic_id}", {
    headers: workspaceHeaders(workspaceId),
    params: { path: { topic_id: topicId } },
  });
  return data!.data;
}

export async function createTopic(workspaceId: string, input: TopicCreate) {
  const { data } = await api.POST("/api/v1/topics", {
    headers: workspaceHeaders(workspaceId),
    body: input,
  });
  return data!.data;
}

export async function updateTopic(
  workspaceId: string,
  topicId: string,
  input: TopicUpdate,
) {
  const { data } = await api.PATCH("/api/v1/topics/{topic_id}", {
    headers: workspaceHeaders(workspaceId),
    params: { path: { topic_id: topicId } },
    body: input,
  });
  return data!.data;
}

export async function listProjects(workspaceId: string, status?: string) {
  const { data } = await api.GET("/api/v1/content-projects", {
    headers: workspaceHeaders(workspaceId),
    params: { query: { status_filter: status } },
  });
  return data?.data ?? [];
}

export async function getProject(workspaceId: string, projectId: string) {
  const { data } = await api.GET("/api/v1/content-projects/{project_id}", {
    headers: workspaceHeaders(workspaceId),
    params: { path: { project_id: projectId } },
  });
  return data!.data;
}

export async function createProject(
  workspaceId: string,
  input: ContentProjectCreate,
) {
  const { data } = await api.POST("/api/v1/content-projects", {
    headers: workspaceHeaders(workspaceId),
    body: input,
  });
  return data!.data;
}

export async function updateProject(
  workspaceId: string,
  projectId: string,
  input: ContentProjectUpdate,
) {
  const { data } = await api.PATCH("/api/v1/content-projects/{project_id}", {
    headers: workspaceHeaders(workspaceId),
    params: { path: { project_id: projectId } },
    body: input,
  });
  return data!.data;
}

export async function transitionProject(
  workspaceId: string,
  projectId: string,
  from: string,
  to: string,
  version: number,
) {
  const { data } = await api.POST(
    "/api/v1/content-projects/{project_id}/transition",
    {
      headers: workspaceHeaders(workspaceId),
      params: { path: { project_id: projectId } },
      body: { from, to, version },
    },
  );
  return data!.data;
}

export async function listScripts(workspaceId: string, projectId: string) {
  const { data } = await api.GET(
    "/api/v1/content-projects/{project_id}/scripts",
    {
      headers: workspaceHeaders(workspaceId),
      params: { path: { project_id: projectId } },
    },
  );
  return data?.data ?? [];
}

export async function createScript(
  workspaceId: string,
  projectId: string,
  input: ScriptCreate,
) {
  const { data } = await api.POST(
    "/api/v1/content-projects/{project_id}/scripts",
    {
      headers: workspaceHeaders(workspaceId),
      params: { path: { project_id: projectId } },
      body: input,
    },
  );
  return data!.data;
}

export async function generateScript(
  workspaceId: string,
  projectId: string,
  projectVersion: number,
  instruction?: string,
) {
  const { data } = await api.POST(
    "/api/v1/content-projects/{project_id}/scripts/generate",
    {
      headers: workspaceHeaders(workspaceId),
      params: { path: { project_id: projectId } },
      body: {
        project_version: projectVersion,
        instruction: instruction || null,
        force: false,
      },
    },
  );
  return data!.data;
}

export async function listAssets(
  workspaceId: string,
  contentProjectId?: string,
) {
  const { data } = await api.GET("/api/v1/assets", {
    headers: workspaceHeaders(workspaceId),
    params: { query: { content_project_id: contentProjectId } },
  });
  return data?.data ?? [];
}

async function sha256(file: File) {
  const bytes = await file.arrayBuffer();
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest))
    .map((item) => item.toString(16).padStart(2, "0"))
    .join("");
}

export async function uploadAsset(
  workspaceId: string,
  file: File,
  projectId: string | undefined,
  assetType: "image" | "video" | "audio" | "subtitle" | "document",
  rightsNote: string,
) {
  const checksum = await sha256(file);
  const { data: intentResponse } = await api.POST("/api/v1/assets/upload-intents", {
    headers: workspaceHeaders(workspaceId),
    body: {
      content_project_id: projectId,
      asset_type: assetType,
      mime_type: file.type || "application/octet-stream",
      size_bytes: file.size,
      checksum,
      source_type: "uploaded",
      rights_note: rightsNote || null,
    },
  });
  const intent = intentResponse!.data;
  const upload = await fetch(intent.upload_url, {
    method: "PUT",
    headers: intent.required_headers,
    body: file,
  });
  if (!upload.ok) throw new Error(`对象存储上传失败（HTTP ${upload.status}）`);
  const { data } = await api.POST("/api/v1/assets/complete", {
    headers: workspaceHeaders(workspaceId),
    body: {
      intent_id: intent.intent_id,
      upload_token: intent.upload_token,
    },
  });
  return data!.data;
}

export async function listPlans(workspaceId: string, status?: string) {
  const { data } = await api.GET("/api/v1/publish-plans", {
    headers: workspaceHeaders(workspaceId),
    params: { query: { status_filter: status } },
  });
  return data?.data ?? [];
}

export async function createPlan(
  workspaceId: string,
  input: PublishPlanCreate,
) {
  const { data } = await api.POST("/api/v1/publish-plans", {
    headers: workspaceHeaders(workspaceId),
    body: input,
  });
  return data!.data;
}

export async function updatePlan(
  workspaceId: string,
  planId: string,
  input: PublishPlanUpdate,
) {
  const { data } = await api.PATCH("/api/v1/publish-plans/{plan_id}", {
    headers: workspaceHeaders(workspaceId),
    params: { path: { plan_id: planId } },
    body: input,
  });
  return data!.data;
}

export async function approvePlan(workspaceId: string, planId: string) {
  const { data } = await api.POST("/api/v1/publish-plans/{plan_id}/approve", {
    headers: workspaceHeaders(workspaceId),
    params: { path: { plan_id: planId } },
  });
  return data!.data;
}

export async function buildPackage(workspaceId: string, planId: string) {
  const { data } = await api.POST("/api/v1/publish-plans/{plan_id}/publish", {
    headers: workspaceHeaders(workspaceId),
    params: { path: { plan_id: planId } },
  });
  return data!.data;
}

export async function markPublished(
  workspaceId: string,
  planId: string,
  input: MarkPublished,
) {
  const { data } = await api.POST(
    "/api/v1/publish-plans/{plan_id}/mark-published",
    {
      headers: workspaceHeaders(workspaceId),
      params: { path: { plan_id: planId } },
      body: input,
    },
  );
  return data!.data;
}

export async function getRecord(workspaceId: string, recordId: string) {
  const { data } = await api.GET("/api/v1/publish-records/{record_id}", {
    headers: workspaceHeaders(workspaceId),
    params: { path: { record_id: recordId } },
  });
  return data!.data;
}

export async function listReviews(workspaceId: string, recordId: string) {
  const { data } = await api.GET(
    "/api/v1/publish-records/{record_id}/reviews",
    {
      headers: workspaceHeaders(workspaceId),
      params: { path: { record_id: recordId } },
    },
  );
  return data?.data ?? [];
}

export async function createReview(
  workspaceId: string,
  recordId: string,
  input: ReviewCreate,
) {
  const { data } = await api.POST(
    "/api/v1/publish-records/{record_id}/reviews",
    {
      headers: workspaceHeaders(workspaceId),
      params: { path: { record_id: recordId } },
      body: input,
    },
  );
  return data!.data;
}

export async function getToday(workspaceId: string) {
  const { data } = await api.GET("/api/v1/dashboard/today", {
    headers: workspaceHeaders(workspaceId),
  });
  return data!.data;
}

export async function getPerformance(workspaceId: string, days = 30) {
  const { data } = await api.GET("/api/v1/dashboard/performance", {
    headers: workspaceHeaders(workspaceId),
    params: { query: { days } },
  });
  return data!.data;
}

export async function listSavedViews(workspaceId: string, entityType: string) {
  const { data } = await api.GET("/api/v1/saved-views", {
    headers: workspaceHeaders(workspaceId),
    params: { query: { entity_type: entityType } },
  });
  return data?.data ?? [];
}

export async function createSavedView(
  workspaceId: string,
  input: SavedViewCreate,
) {
  const { data } = await api.POST("/api/v1/saved-views", {
    headers: workspaceHeaders(workspaceId),
    body: input,
  });
  return data!.data;
}

export async function unifiedSearch(workspaceId: string, q: string) {
  const { data } = await api.GET("/api/v1/search", {
    headers: workspaceHeaders(workspaceId),
    params: { query: { q, limit: 20 } },
  });
  return data?.data ?? [];
}

export async function listExperiments(workspaceId: string) {
  const { data } = await api.GET("/api/v1/experiments", {
    headers: workspaceHeaders(workspaceId),
  });
  return data?.data ?? [];
}

export async function createExperiment(
  workspaceId: string,
  input: ExperimentCreate,
) {
  const { data } = await api.POST("/api/v1/experiments", {
    headers: workspaceHeaders(workspaceId),
    body: input,
  });
  return data!.data;
}

export async function getExperimentResults(
  workspaceId: string,
  experimentId: string,
) {
  const { data } = await api.GET(
    "/api/v1/experiments/{experiment_id}/results",
    {
      headers: workspaceHeaders(workspaceId),
      params: { path: { experiment_id: experimentId } },
    },
  );
  return data!.data;
}
