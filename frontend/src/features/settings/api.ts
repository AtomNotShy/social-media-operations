import { api, workspaceHeaders } from "@/src/api/client";
import type {
  AIConnection,
  AIConnectionCreate,
  AIConnectionTestResult,
  AIConnectionUpdate,
  AIModelRoute,
  AIModelRouteUpsert,
  AISettings,
  AITaskType,
  ExternalCallsState,
  ProviderHealth,
  QueueHealth,
  Workspace,
  WorkspaceMember,
  WorkspaceMemberAdd,
  WorkspaceMemberUpdate,
  WorkspaceUpdate,
} from "@/src/features/settings/types";

export async function getAISettings(
  workspaceId: string,
): Promise<AISettings> {
  const { data } = await api.GET("/api/v1/ai/settings", {
    params: { header: workspaceHeaders(workspaceId) },
  });
  return data!.data;
}

export async function addAIConnection(
  workspaceId: string,
  input: AIConnectionCreate,
): Promise<AIConnection> {
  const { data } = await api.POST("/api/v1/ai/connections", {
    params: { header: workspaceHeaders(workspaceId) },
    body: input,
  });
  return data!.data;
}

export async function updateAIConnection(
  workspaceId: string,
  connectionId: string,
  input: AIConnectionUpdate,
): Promise<AIConnection> {
  const { data } = await api.PATCH(
    "/api/v1/ai/connections/{connection_id}",
    {
      params: {
        path: { connection_id: connectionId },
        header: workspaceHeaders(workspaceId),
      },
      body: input,
    },
  );
  return data!.data;
}

export async function testAIConnection(
  workspaceId: string,
  connectionId: string,
  model?: string,
): Promise<AIConnectionTestResult> {
  const { data } = await api.POST(
    "/api/v1/ai/connections/{connection_id}/test",
    {
      params: {
        path: { connection_id: connectionId },
        header: workspaceHeaders(workspaceId),
      },
      body: { model: model || null },
    },
  );
  return data!.data;
}

export async function updateAIModelRoute(
  workspaceId: string,
  taskType: AITaskType,
  input: AIModelRouteUpsert,
): Promise<AIModelRoute> {
  const { data } = await api.PUT("/api/v1/ai/routes/{task_type}", {
    params: {
      path: { task_type: taskType },
      header: workspaceHeaders(workspaceId),
    },
    body: input,
  });
  return data!.data;
}

export async function getWorkspace(workspaceId: string): Promise<Workspace> {
  const { data } = await api.GET("/api/v1/workspaces/{workspace_id}", {
    params: { path: { workspace_id: workspaceId } },
  });
  return data!.data;
}

export async function updateWorkspace(
  workspaceId: string,
  input: WorkspaceUpdate,
): Promise<Workspace> {
  const { data } = await api.PATCH("/api/v1/workspaces/{workspace_id}", {
    params: { path: { workspace_id: workspaceId } },
    body: input,
  });
  return data!.data;
}

export async function listMembers(
  workspaceId: string,
): Promise<WorkspaceMember[]> {
  const { data } = await api.GET(
    "/api/v1/workspaces/{workspace_id}/members",
    {
      params: {
        path: { workspace_id: workspaceId },
        header: workspaceHeaders(workspaceId),
      },
    },
  );
  return data?.data ?? [];
}

export async function addMember(
  workspaceId: string,
  input: WorkspaceMemberAdd,
): Promise<WorkspaceMember> {
  const { data } = await api.POST(
    "/api/v1/workspaces/{workspace_id}/members",
    {
      params: {
        path: { workspace_id: workspaceId },
        header: workspaceHeaders(workspaceId),
      },
      body: input,
    },
  );
  return data!.data;
}

export async function updateMember(
  workspaceId: string,
  userId: string,
  input: WorkspaceMemberUpdate,
): Promise<WorkspaceMember> {
  const { data } = await api.PATCH(
    "/api/v1/workspaces/{workspace_id}/members/{user_id}",
    {
      params: {
        path: { workspace_id: workspaceId, user_id: userId },
        header: workspaceHeaders(workspaceId),
      },
      body: input,
    },
  );
  return data!.data;
}

export async function removeMember(
  workspaceId: string,
  userId: string,
): Promise<void> {
  await api.DELETE(
    "/api/v1/workspaces/{workspace_id}/members/{user_id}",
    {
      params: {
        path: { workspace_id: workspaceId, user_id: userId },
        header: workspaceHeaders(workspaceId),
      },
    },
  );
}

export async function pauseExternalCalls(
  workspaceId: string,
  reason: string,
): Promise<ExternalCallsState> {
  const { data } = await api.POST(
    "/api/v1/workspaces/{workspace_id}/external-calls/pause",
    {
      params: { path: { workspace_id: workspaceId } },
      body: { reason },
    },
  );
  return data!.data;
}

export async function resumeExternalCalls(
  workspaceId: string,
): Promise<ExternalCallsState> {
  const { data } = await api.POST(
    "/api/v1/workspaces/{workspace_id}/external-calls/resume",
    { params: { path: { workspace_id: workspaceId } } },
  );
  return data!.data;
}

export async function getQueueHealth(
  workspaceId: string,
): Promise<QueueHealth> {
  const { data } = await api.GET("/api/v1/system/queue-health", {
    params: { header: workspaceHeaders(workspaceId) },
  });
  return data!.data;
}

export async function getProviderHealth(
  workspaceId: string,
): Promise<ProviderHealth> {
  const { data } = await api.GET("/api/v1/system/provider-health", {
    params: { header: workspaceHeaders(workspaceId) },
  });
  return data!.data as ProviderHealth;
}
