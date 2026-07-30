import type { components } from "@/src/api/generated/schema";

export type Workspace = components["schemas"]["WorkspaceRead"];
export type WorkspaceUpdate = components["schemas"]["WorkspaceUpdate"];
export type WorkspaceMember = components["schemas"]["WorkspaceMemberRead"];
export type WorkspaceMemberAdd = components["schemas"]["WorkspaceMemberAdd"];
export type WorkspaceMemberUpdate =
  components["schemas"]["WorkspaceMemberUpdate"];
export type ExternalCallsState =
  components["schemas"]["ExternalCallsStateRead"];
export type QueueHealth = components["schemas"]["QueueHealthRead"];
export type AISettings = components["schemas"]["AISettingsRead"];
export type AIConnection = components["schemas"]["AIConnectionRead"];
export type AIConnectionCreate = components["schemas"]["AIConnectionCreate"];
export type AIConnectionUpdate = components["schemas"]["AIConnectionUpdate"];
export type AIConnectionTestResult =
  components["schemas"]["AIConnectionTestResult"];
export type AIModelRoute = components["schemas"]["AIModelRouteRead"];
export type AIModelRouteUpsert =
  components["schemas"]["AIModelRouteUpsert"];
export type AITaskType = "l1" | "l2" | "generation";

export type ProviderEndpointHealth = {
  endpoint_key: string;
  request_count_24h: number;
  success_count_24h: number;
  failure_count_24h: number;
  average_latency_ms_24h: number | null;
  estimated_cost_usd_24h: string;
  last_request_at: string | null;
  circuit: {
    state: string;
    consecutive_failures: number;
    retry_after: string | null;
    last_error_code: string | null;
  };
};

export type ProviderHealth = {
  provider: string;
  endpoints: ProviderEndpointHealth[];
};

export function externalCallsState(workspace?: Workspace): {
  paused: boolean;
  reason: string | null;
  changedAt: string | null;
} {
  const value = workspace?.settings.external_calls;
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return { paused: false, reason: null, changedAt: null };
  }
  const state = value as Record<string, unknown>;
  return {
    paused: state.paused === true,
    reason: typeof state.reason === "string" ? state.reason : null,
    changedAt:
      typeof state.changed_at === "string" ? state.changed_at : null,
  };
}
