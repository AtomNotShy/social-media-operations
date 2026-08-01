"use client";

import { useEffect } from "react";
import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { queryKeys, type TrackedProfileFilters } from "@/src/api/query-keys";
import {
  changeTrackedProfileStatus,
  createTrackedProfile,
  deleteTrackedProfile,
  getTrackedProfile,
  getTrackedProfileOverview,
  listTrackedProfiles,
  syncTrackedProfile,
  updateTrackedProfile,
} from "@/src/features/tracked-profiles/api";
import type {
  Job,
  TrackedProfile,
  TrackedProfileCreate,
  TrackedProfileOverview,
  TrackedProfileUpdate,
} from "@/src/features/tracked-profiles/types";
import {
  demoContents,
  demoInspirations,
  demoJobs,
  demoProfiles,
} from "@/src/test/fixtures";
import { contentCoverUrl } from "@/src/features/inspirations/presentation";

export function useTrackedProfiles(
  workspaceId: string,
  filters: TrackedProfileFilters,
) {
  return useQuery({
    queryKey: queryKeys.trackedProfiles.list(workspaceId, filters),
    queryFn: async () => {
      const profiles =
        workspaceId === "demo"
          ? structuredClone(demoProfiles)
          : await listTrackedProfiles(workspaceId, filters.active);
      const query = filters.q?.trim().toLowerCase();
      return query
        ? profiles.filter((item) =>
            [item.display_name, item.handle, item.platform].some((value) =>
              value?.toLowerCase().includes(query),
            ),
          )
        : profiles;
    },
  });
}

export function useTrackedProfile(
  workspaceId: string,
  profileId: string,
) {
  return useQuery({
    queryKey: queryKeys.trackedProfiles.detail(workspaceId, profileId),
    queryFn: async () => {
      if (workspaceId === "demo") {
        const profile = structuredClone(demoProfiles).find(
          (item) => item.id === profileId,
        );
        if (!profile) throw new Error("没有找到这个对标账号。");
        return profile;
      }
      return getTrackedProfile(workspaceId, profileId);
    },
  });
}

export function useTrackedProfileOverview(
  workspaceId: string,
  profileId: string,
  windowDays = 30,
) {
  const client = useQueryClient();
  const query = useQuery({
    queryKey: queryKeys.trackedProfiles.overview(
      workspaceId,
      profileId,
      windowDays,
    ),
    queryFn: async () => {
      if (workspaceId !== "demo") {
        return getTrackedProfileOverview(
          workspaceId,
          profileId,
          windowDays,
          12,
        );
      }

      const profile = structuredClone(demoProfiles).find(
        (item) => item.id === profileId,
      );
      if (!profile) throw new Error("没有找到这个对标账号。");
      const contents = structuredClone(demoContents).filter(
        (item) => item.tracked_profile_id === profileId,
      );
      const overviewContents = contents.map((content) => {
        const inspiration = demoInspirations.find(
          (item) => item.content.id === content.id,
        );
        return {
          id: content.id,
          platform: content.platform,
          external_id: content.external_id,
          canonical_url: content.canonical_url,
          content_type: content.content_type,
          title: content.title,
          cover_url: contentCoverUrl(content.media_manifest),
          published_at: content.published_at,
          first_seen_at: content.first_seen_at,
          latest_metrics: inspiration?.latest_metrics
            ? { ...inspiration.latest_metrics, downloads: null }
            : null,
          latest_score: inspiration?.latest_score
            ? { ...inspiration.latest_score, tier: null }
            : null,
          in_inspiration_library: Boolean(inspiration),
          inspiration_id: inspiration?.id ?? null,
        };
      });
      const gradeDistribution = overviewContents.reduce(
        (distribution, content) => {
          const grade = content.latest_score?.grade.toLowerCase();
          if (
            grade === "t1" ||
            grade === "t2" ||
            grade === "t3" ||
            grade === "qualified"
          ) {
            distribution[grade] += 1;
          } else {
            distribution.normal += 1;
          }
          return distribution;
        },
        { t1: 0, t2: 0, t3: 0, qualified: 0, normal: 0 },
      );
      return {
        profile,
        window_days: windowDays,
        total_content_count: overviewContents.length,
        recent_content_count: overviewContents.length,
        grade_distribution: gradeDistribution,
        contents: overviewContents,
      } satisfies TrackedProfileOverview;
    },
    refetchInterval: (query) =>
      workspaceId !== "demo" &&
      ["pending", "running", "syncing"].includes(
        query.state.data?.profile.sync_status ?? "",
      )
        ? 5_000
        : false,
  });

  useEffect(() => {
    const currentProfile = query.data?.profile;
    if (!currentProfile) return;
    client.setQueryData(
      queryKeys.trackedProfiles.detail(workspaceId, profileId),
      currentProfile,
    );
    client.setQueriesData<TrackedProfile[]>(
      { queryKey: queryKeys.trackedProfiles.lists(workspaceId) },
      (current) =>
        current?.map((item) =>
          item.id === currentProfile.id ? currentProfile : item,
        ),
    );
  }, [client, profileId, query.data?.profile, workspaceId]);

  return query;
}

function updateOverviewProfile(
  client: ReturnType<typeof useQueryClient>,
  workspaceId: string,
  profile: TrackedProfile,
) {
  client.setQueriesData<TrackedProfileOverview>(
    {
      queryKey: [
        ...queryKeys.trackedProfiles.detail(workspaceId, profile.id),
        "overview",
      ],
    },
    (current) => (current ? { ...current, profile } : current),
  );
}

export function useUpdateTrackedProfile(
  workspaceId: string,
  profileId: string,
) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (input: TrackedProfileUpdate) => {
      if (workspaceId !== "demo") {
        return updateTrackedProfile(workspaceId, profileId, input);
      }
      const current = client.getQueryData<TrackedProfile>(
        queryKeys.trackedProfiles.detail(workspaceId, profileId),
      );
      const fallback = structuredClone(demoProfiles).find(
        (item) => item.id === profileId,
      );
      if (!current && !fallback) throw new Error("没有找到这个对标账号。");
      const base = current ?? fallback!;
      return {
        ...base,
        display_name: input.display_name ?? base.display_name,
        priority: input.priority ?? base.priority,
        updated_at: new Date().toISOString(),
      } satisfies TrackedProfile;
    },
    onSuccess: (updated) => {
      client.setQueryData(
        queryKeys.trackedProfiles.detail(workspaceId, profileId),
        updated,
      );
      client.setQueriesData<TrackedProfile[]>(
        { queryKey: queryKeys.trackedProfiles.lists(workspaceId) },
        (current) =>
          current?.map((item) => (item.id === updated.id ? updated : item)),
      );
      updateOverviewProfile(client, workspaceId, updated);
    },
  });
}

export function useCreateTrackedProfile(
  workspaceId: string,
  onCreated?: () => void,
) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (input: TrackedProfileCreate) => {
      if (workspaceId !== "demo") {
        return createTrackedProfile(workspaceId, input);
      }
      const now = new Date().toISOString();
      return {
        ...input,
        id: crypto.randomUUID(),
        workspace_id: "7391ea11-9464-456d-bdc8-f7aa5ebf4d30",
        follower_count_latest: null,
        avatar_url: null,
        scan_policy_id:
          input.scan_policy_id ??
          "19ca8d53-85db-49c7-b9d0-e5d7f73dc82f",
        last_synced_at: null,
        next_scan_at: null,
        sync_status: "idle",
        active: true,
        created_at: now,
        updated_at: now,
        handle: input.handle ?? null,
      } satisfies TrackedProfile;
    },
    onSuccess: () => {
      client.invalidateQueries({
        queryKey: queryKeys.trackedProfiles.lists(workspaceId),
      });
      onCreated?.();
    },
  });
}

export function useToggleTrackedProfile(workspaceId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (profile: TrackedProfile) => {
      if (workspaceId !== "demo") {
        return changeTrackedProfileStatus(workspaceId, profile);
      }
      return {
        ...profile,
        active: !profile.active,
        sync_status: profile.active ? "paused" : "idle",
        updated_at: new Date().toISOString(),
      } satisfies TrackedProfile;
    },
    onSuccess: (updated) => {
      client.setQueryData(
        queryKeys.trackedProfiles.detail(workspaceId, updated.id),
        updated,
      );
      updateOverviewProfile(client, workspaceId, updated);
      client.invalidateQueries({
        queryKey: queryKeys.trackedProfiles.lists(workspaceId),
      });
    },
  });
}

export function useDeleteTrackedProfile(workspaceId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (profile: TrackedProfile) => {
      if (workspaceId !== "demo") {
        await deleteTrackedProfile(workspaceId, profile.id);
        return {
          ...profile,
          active: false,
          sync_status: "paused",
          next_scan_at: null,
        };
      }
      return {
        ...profile,
        active: false,
        sync_status: "paused",
        next_scan_at: null,
        updated_at: new Date().toISOString(),
      } satisfies TrackedProfile;
    },
    onSuccess: (updated) => {
      client.setQueryData(
        queryKeys.trackedProfiles.detail(workspaceId, updated.id),
        updated,
      );
      updateOverviewProfile(client, workspaceId, updated);
      client.invalidateQueries({
        queryKey: queryKeys.trackedProfiles.lists(workspaceId),
      });
    },
  });
}

export function useSyncTrackedProfile(workspaceId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (profile: TrackedProfile) => {
      if (workspaceId !== "demo") {
        return syncTrackedProfile(workspaceId, profile.id);
      }
      return { id: crypto.randomUUID(), status: "pending" };
    },
    onSuccess: (accepted, profile) => {
      const pendingProfile = {
        ...profile,
        sync_status: accepted.status,
      } satisfies TrackedProfile;
      client.setQueryData(
        queryKeys.trackedProfiles.detail(workspaceId, profile.id),
        pendingProfile,
      );
      client.setQueriesData<TrackedProfile[]>(
        { queryKey: queryKeys.trackedProfiles.lists(workspaceId) },
        (current) =>
          current?.map((item) =>
            item.id === profile.id ? pendingProfile : item,
          ),
      );
      updateOverviewProfile(client, workspaceId, pendingProfile);
      client.invalidateQueries({ queryKey: queryKeys.jobs.all(workspaceId) });
      if (workspaceId === "demo") {
        const now = new Date().toISOString();
        const job: Job = {
          id: accepted.id,
          workspace_id: profile.workspace_id,
          job_type: "PROFILE_SCAN",
          status: accepted.status,
          priority: profile.priority,
          attempt: 0,
          max_attempts: 3,
          run_after: now,
          last_error_code: null,
          last_error_message: null,
          result: null,
          created_at: now,
          finished_at: null,
        };
        client.setQueryData<Job[]>(
          queryKeys.jobs.all(workspaceId),
          (current = structuredClone(demoJobs)) => [job, ...current],
        );
      }
    },
  });
}
