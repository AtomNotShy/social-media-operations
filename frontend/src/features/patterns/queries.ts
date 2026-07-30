"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { queryKeys } from "@/src/api/query-keys";
import {
  createPattern,
  createPatternsFromAnalysis,
  getPattern,
  listPatterns,
  transitionPattern,
  updatePattern,
} from "@/src/features/patterns/api";
import type {
  Pattern,
  PatternCreate,
  PatternUpdate,
} from "@/src/features/patterns/types";
import { demoPatterns } from "@/src/test/fixtures";

export function usePatterns(workspaceId: string, status?: string) {
  return useQuery({
    queryKey: queryKeys.patterns.list(workspaceId, status),
    queryFn: async () => {
      const patterns =
        workspaceId === "demo"
          ? structuredClone(demoPatterns)
          : await listPatterns(workspaceId, status);
      return status ? patterns.filter((item) => item.status === status) : patterns;
    },
    staleTime: 30_000,
  });
}

export function usePattern(workspaceId: string, patternId: string) {
  return useQuery({
    queryKey: queryKeys.patterns.detail(workspaceId, patternId),
    queryFn: async () => {
      if (workspaceId !== "demo") return getPattern(workspaceId, patternId);
      const pattern = structuredClone(demoPatterns).find(
        (item) => item.id === patternId,
      );
      if (!pattern) throw new Error("没有找到这个可复用模式。");
      return pattern;
    },
  });
}

export function useCreatePattern(workspaceId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (input: PatternCreate) => {
      if (workspaceId !== "demo") return createPattern(workspaceId, input);
      const now = new Date().toISOString();
      return {
        ...input,
        id: crypto.randomUUID(),
        applicable_channels: input.applicable_channels ?? [],
        source_content_ids: input.source_content_ids ?? [],
        evidence: input.evidence ?? {},
        status: "draft" as const,
        created_by: null,
        created_at: now,
        updated_at: now,
      } satisfies Pattern;
    },
    onSuccess: (created) => {
      client.setQueriesData<Pattern[]>(
        { queryKey: queryKeys.patterns.all(workspaceId) },
        (items = structuredClone(demoPatterns)) => [created, ...items],
      );
    },
  });
}

export function useUpdatePattern(
  workspaceId: string,
  patternId: string,
) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (input: PatternUpdate) => {
      if (workspaceId !== "demo") {
        return updatePattern(workspaceId, patternId, input);
      }
      const current =
        client.getQueryData<Pattern>(
          queryKeys.patterns.detail(workspaceId, patternId),
        ) ??
        structuredClone(demoPatterns).find((item) => item.id === patternId);
      if (!current) throw new Error("没有找到这个可复用模式。");
      return {
        ...current,
        ...input,
        updated_at: new Date().toISOString(),
      } as Pattern;
    },
    onSuccess: (updated) => {
      client.setQueryData(
        queryKeys.patterns.detail(workspaceId, patternId),
        updated,
      );
      client.invalidateQueries({ queryKey: queryKeys.patterns.all(workspaceId) });
    },
  });
}

export function useTransitionPattern(
  workspaceId: string,
  patternId: string,
) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (target: "validated" | "retired") => {
      if (workspaceId !== "demo") {
        return transitionPattern(workspaceId, patternId, target);
      }
      const current =
        client.getQueryData<Pattern>(
          queryKeys.patterns.detail(workspaceId, patternId),
        ) ??
        structuredClone(demoPatterns).find((item) => item.id === patternId);
      if (!current) throw new Error("没有找到这个可复用模式。");
      return {
        ...current,
        status: target,
        updated_at: new Date().toISOString(),
      };
    },
    onSuccess: (updated) => {
      client.setQueryData(
        queryKeys.patterns.detail(workspaceId, patternId),
        updated,
      );
      client.invalidateQueries({ queryKey: queryKeys.patterns.all(workspaceId) });
    },
  });
}

export function useCreatePatternsFromAnalysis(
  workspaceId: string,
  analysisId?: string,
) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      if (!analysisId) throw new Error("没有可用于提炼模式的成功分析。");
      if (workspaceId !== "demo") {
        return createPatternsFromAnalysis(workspaceId, analysisId);
      }
      return structuredClone(demoPatterns).slice(0, 1);
    },
    onSuccess: () => {
      client.invalidateQueries({ queryKey: queryKeys.patterns.all(workspaceId) });
    },
  });
}
