import { api, workspaceHeaders } from "@/src/api/client";
import type {
  PatternCreate,
  PatternUpdate,
} from "@/src/features/patterns/types";

export async function listPatterns(workspaceId: string, status?: string) {
  const { data } = await api.GET("/api/v1/patterns", {
    headers: workspaceHeaders(workspaceId),
    params: { query: { status } },
  });
  return data?.data ?? [];
}

export async function getPattern(workspaceId: string, patternId: string) {
  const { data } = await api.GET("/api/v1/patterns/{pattern_id}", {
    headers: workspaceHeaders(workspaceId),
    params: { path: { pattern_id: patternId } },
  });
  return data!.data;
}

export async function createPattern(
  workspaceId: string,
  input: PatternCreate,
) {
  const { data } = await api.POST("/api/v1/patterns", {
    headers: workspaceHeaders(workspaceId),
    body: input,
  });
  return data!.data;
}

export async function updatePattern(
  workspaceId: string,
  patternId: string,
  input: PatternUpdate,
) {
  const { data } = await api.PATCH("/api/v1/patterns/{pattern_id}", {
    headers: workspaceHeaders(workspaceId),
    params: { path: { pattern_id: patternId } },
    body: input,
  });
  return data!.data;
}

export async function transitionPattern(
  workspaceId: string,
  patternId: string,
  target: "validated" | "retired",
) {
  const path =
    target === "validated"
      ? "/api/v1/patterns/{pattern_id}/validate"
      : "/api/v1/patterns/{pattern_id}/retire";
  const { data } = await api.POST(path, {
    headers: workspaceHeaders(workspaceId),
    params: { path: { pattern_id: patternId } },
  });
  return data!.data;
}

export async function createPatternsFromAnalysis(
  workspaceId: string,
  analysisId: string,
) {
  const { data } = await api.POST(
    "/api/v1/patterns/from-analysis/{analysis_id}",
    {
      headers: workspaceHeaders(workspaceId),
      params: { path: { analysis_id: analysisId } },
    },
  );
  return data!.data;
}
