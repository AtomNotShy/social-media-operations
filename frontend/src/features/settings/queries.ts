"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { queryKeys } from "@/src/api/query-keys";
import * as service from "@/src/features/settings/api";
import {
  demoAISettings,
  demoMembers,
  demoProviderHealth,
  demoQueueHealth,
  demoWorkspace,
} from "@/src/features/settings/fixtures";
import type {
  AIConnection,
  AIConnectionCreate,
  AIConnectionUpdate,
  AIModelRoute,
  AIModelRouteUpsert,
  AISettings,
  AITaskType,
  ExternalCallsState,
  Workspace,
  WorkspaceMember,
  WorkspaceMemberAdd,
  WorkspaceMemberUpdate,
  WorkspaceUpdate,
} from "@/src/features/settings/types";

function clone<T>(value: T): T {
  return structuredClone(value);
}

export function useWorkspaceSettings(workspaceId: string) {
  return useQuery({
    queryKey: queryKeys.workspace(workspaceId),
    queryFn: () =>
      workspaceId === "demo"
        ? clone(demoWorkspace)
        : service.getWorkspace(workspaceId),
  });
}

export function useAISettings(workspaceId: string) {
  return useQuery({
    queryKey: queryKeys.settings.ai(workspaceId),
    queryFn: () =>
      workspaceId === "demo"
        ? clone(demoAISettings)
        : service.getAISettings(workspaceId),
  });
}

export function useAddAIConnection(workspaceId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (input: AIConnectionCreate) => {
      if (workspaceId !== "demo") {
        return service.addAIConnection(workspaceId, input);
      }
      const provider = demoAISettings.providers.find(
        (item) => item.provider === input.provider,
      );
      return {
        id: crypto.randomUUID(),
        name: input.name,
        provider: input.provider,
        base_url: input.base_url || provider?.default_base_url || "",
        enabled: true,
        timeout_seconds: input.timeout_seconds,
        json_mode: input.json_mode,
        api_key_configured: Boolean(input.api_key),
        api_key_masked: input.api_key
          ? `••••${input.api_key.slice(-4).toUpperCase()}`
          : null,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      } satisfies AIConnection;
    },
    onSuccess: (connection) => {
      if (workspaceId !== "demo") {
        client.invalidateQueries({
          queryKey: queryKeys.settings.ai(workspaceId),
        });
        return;
      }
      client.setQueryData<AISettings>(
        queryKeys.settings.ai(workspaceId),
        (current) =>
          current
            ? { ...current, connections: [...current.connections, connection] }
            : current,
      );
    },
  });
}

export function useUpdateAIConnection(workspaceId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async ({
      connection,
      input,
    }: {
      connection: AIConnection;
      input: AIConnectionUpdate;
    }) => {
      if (workspaceId !== "demo") {
        return service.updateAIConnection(
          workspaceId,
          connection.id,
          input,
        );
      }
      return {
        ...connection,
        name: input.name ?? connection.name,
        base_url: input.base_url ?? connection.base_url,
        enabled: input.enabled ?? connection.enabled,
        timeout_seconds:
          input.timeout_seconds ?? connection.timeout_seconds,
        json_mode: input.json_mode ?? connection.json_mode,
        api_key_configured: input.clear_api_key
          ? false
          : Boolean(input.api_key) || connection.api_key_configured,
        api_key_masked: input.clear_api_key
          ? null
          : input.api_key
            ? `••••${input.api_key.slice(-4).toUpperCase()}`
            : connection.api_key_masked,
        updated_at: new Date().toISOString(),
      } satisfies AIConnection;
    },
    onSuccess: (updated) =>
      client.setQueryData<AISettings>(
        queryKeys.settings.ai(workspaceId),
        (current) =>
          current
            ? {
                ...current,
                connections: current.connections.map((item) =>
                  item.id === updated.id ? updated : item,
                ),
              }
            : current,
      ),
  });
}

export function useTestAIConnection(workspaceId: string) {
  return useMutation({
    mutationFn: ({
      connection,
      model,
    }: {
      connection: AIConnection;
      model?: string;
    }) =>
      workspaceId === "demo"
        ? Promise.resolve({
            ok: true,
            provider: connection.provider,
            base_url: connection.base_url,
            latency_ms: 428,
            available_models: model ? [model] : ["deepseek-chat"],
            requested_model_available: model ? true : null,
          })
        : service.testAIConnection(workspaceId, connection.id, model),
  });
}

export function useUpdateAIModelRoute(workspaceId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async ({
      taskType,
      input,
    }: {
      taskType: AITaskType;
      input: AIModelRouteUpsert;
    }) => {
      if (workspaceId !== "demo") {
        return service.updateAIModelRoute(workspaceId, taskType, input);
      }
      const settings = client.getQueryData<AISettings>(
        queryKeys.settings.ai(workspaceId),
      );
      const connection = settings?.connections.find(
        (item) => item.id === input.connection_id,
      );
      if (!connection) throw new Error("请选择可用的 AI 连接。");
      return {
        task_type: taskType,
        connection_id: connection.id,
        connection_name: connection.name,
        provider: connection.provider,
        model: input.model,
        temperature: String(input.temperature),
        max_tokens: input.max_tokens,
        input_cost_per_million_usd: String(
          input.input_cost_per_million_usd,
        ),
        output_cost_per_million_usd: String(
          input.output_cost_per_million_usd,
        ),
        configured: true,
      } satisfies AIModelRoute;
    },
    onSuccess: (route) =>
      client.setQueryData<AISettings>(
        queryKeys.settings.ai(workspaceId),
        (current) =>
          current
            ? {
                ...current,
                routes: [
                  ...current.routes.filter(
                    (item) => item.task_type !== route.task_type,
                  ),
                  route,
                ],
              }
            : current,
      ),
  });
}

export function useUpdateWorkspace(workspaceId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (input: WorkspaceUpdate) => {
      if (workspaceId !== "demo") {
        return service.updateWorkspace(workspaceId, input);
      }
      const current =
        client.getQueryData<Workspace>(queryKeys.workspace(workspaceId)) ??
        clone(demoWorkspace);
      return {
        ...current,
        ...input,
        updated_at: new Date().toISOString(),
      } as Workspace;
    },
    onSuccess: (workspace) => {
      client.setQueryData(queryKeys.workspace(workspaceId), workspace);
      client.invalidateQueries({ queryKey: queryKeys.workspaces });
    },
  });
}

export function useMembers(workspaceId: string, enabled: boolean) {
  return useQuery({
    queryKey: queryKeys.settings.members(workspaceId),
    queryFn: () =>
      workspaceId === "demo"
        ? clone(demoMembers)
        : service.listMembers(workspaceId),
    enabled,
  });
}

export function useAddMember(workspaceId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (input: WorkspaceMemberAdd) => {
      if (workspaceId !== "demo") return service.addMember(workspaceId, input);
      return {
        id: crypto.randomUUID(),
        role: input.role,
        created_at: new Date().toISOString(),
        user: {
          id: input.user_id,
          display_name: "新成员",
          email: null,
          external_subject: `demo-${input.user_id}`,
          status: "active",
        },
      } satisfies WorkspaceMember;
    },
    onSuccess: (member) =>
      client.setQueryData<WorkspaceMember[]>(
        queryKeys.settings.members(workspaceId),
        (current = []) => [...current, member],
      ),
  });
}

export function useUpdateMember(workspaceId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async ({
      userId,
      input,
    }: {
      userId: string;
      input: WorkspaceMemberUpdate;
    }) => {
      if (workspaceId !== "demo") {
        return service.updateMember(workspaceId, userId, input);
      }
      const member = client
        .getQueryData<WorkspaceMember[]>(
          queryKeys.settings.members(workspaceId),
        )
        ?.find((item) => item.user.id === userId);
      if (!member) throw new Error("找不到要更新的成员。");
      return { ...member, role: input.role };
    },
    onSuccess: (result, variables) =>
      client.setQueryData<WorkspaceMember[]>(
        queryKeys.settings.members(workspaceId),
        (current = []) =>
          current.map((member) =>
            member.user.id === variables.userId
              ? { ...member, role: variables.input.role }
              : member,
          ),
      ),
  });
}

export function useRemoveMember(workspaceId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (userId: string) =>
      workspaceId === "demo"
        ? Promise.resolve()
        : service.removeMember(workspaceId, userId),
    onSuccess: (_, userId) =>
      client.setQueryData<WorkspaceMember[]>(
        queryKeys.settings.members(workspaceId),
        (current = []) =>
          current.filter((member) => member.user.id !== userId),
      ),
  });
}

export function useExternalCallsAction(workspaceId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async ({
      action,
      reason,
    }: {
      action: "pause" | "resume";
      reason?: string;
    }) => {
      if (workspaceId !== "demo") {
        return action === "pause"
          ? service.pauseExternalCalls(workspaceId, reason ?? "")
          : service.resumeExternalCalls(workspaceId);
      }
      return {
        paused: action === "pause",
        reason: action === "pause" ? reason ?? null : null,
        changed_at: new Date().toISOString(),
        changed_by: demoMembers[0].user.id,
      } satisfies ExternalCallsState;
    },
    onSuccess: (state) =>
      client.setQueryData<Workspace>(
        queryKeys.workspace(workspaceId),
        (current) =>
          current
            ? {
                ...current,
                settings: {
                  ...current.settings,
                  external_calls: state,
                },
              }
            : current,
      ),
  });
}

export function useProviderHealth(workspaceId: string) {
  return useQuery({
    queryKey: queryKeys.settings.providerHealth(workspaceId),
    queryFn: () =>
      workspaceId === "demo"
        ? clone(demoProviderHealth)
        : service.getProviderHealth(workspaceId),
    refetchInterval: 60_000,
  });
}

export function useQueueHealth(workspaceId: string) {
  return useQuery({
    queryKey: queryKeys.settings.queueHealth(workspaceId),
    queryFn: () =>
      workspaceId === "demo"
        ? clone(demoQueueHealth)
        : service.getQueueHealth(workspaceId),
    refetchInterval: 30_000,
  });
}
