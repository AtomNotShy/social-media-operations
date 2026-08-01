"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { queryKeys, type InspirationFilters } from "@/src/api/query-keys";
import {
  analyzeInspiration,
  fetchComments,
  getInspiration,
  hydrateInspirationDetail,
  importInspirationURL,
  listAnalyses,
  listComments,
  listInspirations,
  listMetrics,
  listProfileContents,
  listScores,
  listTranscripts,
  recalculateScore,
  setInspirationArchived,
  transcribeInspiration,
  updateInspiration,
  createTopicFromInspiration,
} from "@/src/features/inspirations/api";
import type {
  ImportURLRequest,
  Inspiration,
  InspirationUpdate,
} from "@/src/features/inspirations/types";
import {
  demoAnalyses,
  demoComments,
  demoContents,
  demoInspirations,
  demoScores,
  demoTranscripts,
  demoMetrics,
} from "@/src/test/fixtures";

export function useInspirations(
  workspaceId: string,
  filters: InspirationFilters,
) {
  return useQuery({
    queryKey: queryKeys.inspirations.list(workspaceId, filters),
    queryFn: async () => {
      const items =
        workspaceId === "demo"
          ? structuredClone(demoInspirations)
          : await listInspirations(workspaceId, filters);
      const query = filters.q?.trim().toLowerCase();
      return items.filter(
        (item) =>
          (!filters.platform || item.content.platform === filters.platform) &&
          (!filters.status || item.status === filters.status) &&
          (!query ||
            [
              item.content.title,
              item.content.body_text,
              item.notes,
              item.content.platform,
            ].some((value) => value?.toLowerCase().includes(query))),
      );
    },
  });
}

export function useInspiration(
  workspaceId: string,
  inspirationId: string,
) {
  return useQuery({
    queryKey: queryKeys.inspirations.detail(workspaceId, inspirationId),
    queryFn: async () => {
      if (workspaceId !== "demo") {
        return getInspiration(workspaceId, inspirationId);
      }
      const item = structuredClone(demoInspirations).find(
        (candidate) => candidate.id === inspirationId,
      );
      if (!item) throw new Error("没有找到这条灵感。");
      return item;
    },
  });
}

export function useImportInspiration(workspaceId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (input: ImportURLRequest) => {
      if (workspaceId !== "demo") return importInspirationURL(workspaceId, input);
      return {
        inspiration_id: demoInspirations[0].id,
        external_content_id: demoInspirations[0].content.id,
        existing: false,
        job_id: crypto.randomUUID(),
      };
    },
    onSuccess: () => {
      client.invalidateQueries({
        queryKey: queryKeys.inspirations.all(workspaceId),
      });
      client.invalidateQueries({ queryKey: queryKeys.jobs.all(workspaceId) });
    },
  });
}

export function useUpdateInspiration(
  workspaceId: string,
  inspirationId: string,
) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (input: InspirationUpdate) => {
      if (workspaceId !== "demo") {
        return updateInspiration(workspaceId, inspirationId, input);
      }
      const current =
        client.getQueryData<Inspiration>(
          queryKeys.inspirations.detail(workspaceId, inspirationId),
        ) ??
        structuredClone(demoInspirations).find(
          (item) => item.id === inspirationId,
        );
      if (!current) throw new Error("没有找到这条灵感。");
      return {
        ...current,
        ...input,
        updated_at: new Date().toISOString(),
      } as Inspiration;
    },
    onSuccess: (updated) => {
      client.setQueryData(
        queryKeys.inspirations.detail(workspaceId, inspirationId),
        updated,
      );
      client.setQueriesData<Inspiration[]>(
        { queryKey: queryKeys.inspirations.all(workspaceId) },
        (items) =>
          items?.map((item) => (item.id === updated.id ? updated : item)),
      );
    },
  });
}

export function useArchiveInspiration(
  workspaceId: string,
  inspirationId: string,
) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (archived: boolean) => {
      if (workspaceId !== "demo") {
        return setInspirationArchived(workspaceId, inspirationId, archived);
      }
      const item =
        client.getQueryData<Inspiration>(
          queryKeys.inspirations.detail(workspaceId, inspirationId),
        ) ??
        structuredClone(demoInspirations).find(
          (candidate) => candidate.id === inspirationId,
        );
      if (!item) throw new Error("没有找到这条灵感。");
      return {
        ...item,
        status: archived ? "archived" : "inbox",
        updated_at: new Date().toISOString(),
      };
    },
    onSuccess: (updated) => {
      client.setQueryData(
        queryKeys.inspirations.detail(workspaceId, inspirationId),
        updated,
      );
      client.invalidateQueries({
        queryKey: queryKeys.inspirations.all(workspaceId),
      });
    },
  });
}

export function useInspirationEvidence(
  workspaceId: string,
  inspirationId: string,
) {
  const demo = workspaceId === "demo";
  const hasDemoEvidence =
    demo && inspirationId === demoInspirations[0].id;
  return {
    scores: useQuery({
      queryKey: queryKeys.inspirations.scores(workspaceId, inspirationId),
      queryFn: () =>
        demo
          ? hasDemoEvidence
            ? structuredClone(demoScores)
            : []
          : listScores(workspaceId, inspirationId),
    }),
    metrics: useQuery({
      queryKey: queryKeys.inspirations.metrics(workspaceId, inspirationId),
      queryFn: () =>
        demo
          ? hasDemoEvidence
            ? structuredClone(demoMetrics)
            : []
          : listMetrics(workspaceId, inspirationId),
    }),
    comments: useQuery({
      queryKey: queryKeys.inspirations.comments(workspaceId, inspirationId),
      queryFn: () =>
        demo
          ? hasDemoEvidence
            ? structuredClone(demoComments)
            : []
          : listComments(workspaceId, inspirationId),
    }),
    analyses: useQuery({
      queryKey: queryKeys.inspirations.analyses(workspaceId, inspirationId),
      queryFn: () =>
        demo
          ? hasDemoEvidence
            ? structuredClone(demoAnalyses)
            : []
          : listAnalyses(workspaceId, inspirationId),
    }),
    transcripts: useQuery({
      queryKey: queryKeys.inspirations.transcripts(workspaceId, inspirationId),
      queryFn: () =>
        demo
          ? hasDemoEvidence
            ? structuredClone(demoTranscripts)
            : []
          : listTranscripts(workspaceId, inspirationId),
    }),
  };
}

export function useCreateTopicFromInspiration(
  workspaceId: string,
  inspirationId: string,
) {
  return useMutation({
    mutationFn: async (input: {
      title?: string | null;
      audience_problem?: string | null;
      angle?: string | null;
      hook?: string | null;
      owned_channel_id?: string | null;
    }) => {
      if (workspaceId !== "demo") {
        return createTopicFromInspiration(workspaceId, inspirationId, input);
      }
      const now = new Date().toISOString();
      return {
        id: crypto.randomUUID(),
        owned_channel_id: input.owned_channel_id ?? null,
        title: input.title || "从灵感创建的候选选题",
        audience_problem: input.audience_problem ?? null,
        angle: input.angle ?? null,
        hook: input.hook ?? null,
        evidence_refs: [
          `inspiration:${inspirationId}`,
          `content:${demoInspirations[0].content.id}`,
        ],
        status: "idea",
        version: 1,
        created_by: null,
        created_at: now,
        updated_at: now,
      };
    },
  });
}

export type InspirationAction =
  | "hydrate-detail"
  | "score"
  | "comments"
  | "transcript"
  | "analysis-l1"
  | "analysis-l2";

export function useInspirationAction(
  workspaceId: string,
  inspirationId: string,
) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (action: InspirationAction) => {
      if (workspaceId === "demo") return { action, accepted: true };
      if (action === "hydrate-detail") {
        return {
          action,
          data: await hydrateInspirationDetail(workspaceId, inspirationId),
        };
      }
      if (action === "score") {
        return { action, data: await recalculateScore(workspaceId, inspirationId) };
      }
      if (action === "comments") {
        return { action, data: await fetchComments(workspaceId, inspirationId) };
      }
      if (action === "transcript") {
        return {
          action,
          data: await transcribeInspiration(workspaceId, inspirationId),
        };
      }
      return {
        action,
        data: await analyzeInspiration(
          workspaceId,
          inspirationId,
          action === "analysis-l2" ? "l2" : "l1",
        ),
      };
    },
    onSuccess: (_, action) => {
      const key =
        action === "hydrate-detail"
          ? queryKeys.inspirations.detail(workspaceId, inspirationId)
          : action === "score"
            ? queryKeys.inspirations.scores(workspaceId, inspirationId)
            : action === "comments"
              ? queryKeys.inspirations.comments(workspaceId, inspirationId)
              : action === "transcript"
                ? queryKeys.inspirations.transcripts(workspaceId, inspirationId)
                : queryKeys.inspirations.analyses(workspaceId, inspirationId);
      client.invalidateQueries({ queryKey: key });
      if (action === "hydrate-detail") {
        client.invalidateQueries({
          queryKey: queryKeys.inspirations.metrics(workspaceId, inspirationId),
        });
      }
      client.invalidateQueries({ queryKey: queryKeys.jobs.all(workspaceId) });
    },
  });
}

export function useProfileContents(workspaceId: string, profileId: string) {
  return useQuery({
    queryKey: queryKeys.trackedProfiles.contents(workspaceId, profileId),
    queryFn: () =>
      workspaceId === "demo"
        ? structuredClone(demoContents).filter(
            (item) => item.tracked_profile_id === profileId,
          )
        : listProfileContents(workspaceId, profileId),
  });
}
