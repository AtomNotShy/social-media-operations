import type { components } from "@/src/api/generated/schema";

export type Me = components["schemas"]["MeRead"];
export type Workspace = components["schemas"]["WorkspaceRead"];
export type WorkspaceCreate = components["schemas"]["WorkspaceCreate"];
export type WorkspaceRole = "owner" | "editor" | "viewer";
