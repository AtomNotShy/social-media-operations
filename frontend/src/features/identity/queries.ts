"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { queryKeys } from "@/src/api/query-keys";
import {
  createWorkspace,
  getMe,
  listWorkspaces,
} from "@/src/features/identity/api";
import type {
  Workspace,
  WorkspaceCreate,
  WorkspaceRole,
} from "@/src/features/identity/types";
import {
  canEditWorkspace,
  canManageWorkspace,
} from "@/src/features/identity/permissions";

export function useMe(enabled = true) {
  return useQuery({
    queryKey: queryKeys.me,
    queryFn: getMe,
    enabled,
    staleTime: 5 * 60_000,
  });
}

export function useWorkspaces(enabled = true) {
  return useQuery({
    queryKey: queryKeys.workspaces,
    queryFn: listWorkspaces,
    enabled,
    staleTime: 5 * 60_000,
  });
}

export function useCreateWorkspace() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: WorkspaceCreate) => createWorkspace(input),
    onSuccess: (workspace) => {
      client.setQueryData<Workspace[]>(queryKeys.workspaces, (current = []) => [
        ...current,
        workspace,
      ]);
      client.invalidateQueries({ queryKey: queryKeys.me });
    },
  });
}

export function useWorkspaceRole(workspaceId: string) {
  const me = useMe(workspaceId !== "demo");
  const role =
    workspaceId === "demo"
      ? "owner"
      : me.data?.memberships.find(
          (membership) => membership.workspace_id === workspaceId,
        )?.role;
  return {
    ...me,
    role: role as WorkspaceRole | undefined,
    canEdit: canEditWorkspace(role as WorkspaceRole | undefined),
    isOwner: canManageWorkspace(role as WorkspaceRole | undefined),
  };
}
