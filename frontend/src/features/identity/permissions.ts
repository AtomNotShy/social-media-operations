import type { WorkspaceRole } from "@/src/features/identity/types";

export function canEditWorkspace(role?: WorkspaceRole) {
  return role === "owner" || role === "editor";
}

export function canManageWorkspace(role?: WorkspaceRole) {
  return role === "owner";
}
