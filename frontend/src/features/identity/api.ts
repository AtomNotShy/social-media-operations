import { api } from "@/src/api/client";
import type {
  Me,
  Workspace,
  WorkspaceCreate,
} from "@/src/features/identity/types";

export async function getMe(): Promise<Me> {
  const { data } = await api.GET("/api/v1/me");
  return data!.data;
}

export async function listWorkspaces(): Promise<Workspace[]> {
  const { data } = await api.GET("/api/v1/workspaces");
  return data?.data ?? [];
}

export async function createWorkspace(
  input: WorkspaceCreate,
): Promise<Workspace> {
  const { data } = await api.POST("/api/v1/workspaces", { body: input });
  return data!.data;
}
