"use client";

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
  listTrackedProfiles,
  syncTrackedProfile,
  updateTrackedProfile,
} from "@/src/features/tracked-profiles/api";
import type {
  Job,
  TrackedProfile,
  TrackedProfileCreate,
  TrackedProfileUpdate,
} from "@/src/features/tracked-profiles/types";
import { demoJobs, demoProfiles } from "@/src/test/fixtures";

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
        { queryKey: queryKeys.trackedProfiles.all(workspaceId) },
        (current) =>
          current?.map((item) => (item.id === updated.id ? updated : item)),
      );
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
    onSuccess: (created) => {
      client.setQueriesData<TrackedProfile[]>(
        { queryKey: queryKeys.trackedProfiles.all(workspaceId) },
        (current) => (current ? [created, ...current] : [created]),
      );
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
      client.setQueriesData<TrackedProfile[]>(
        { queryKey: queryKeys.trackedProfiles.all(workspaceId) },
        (current) =>
          current?.map((item) => (item.id === updated.id ? updated : item)),
      );
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
      client.setQueriesData<TrackedProfile[]>(
        { queryKey: queryKeys.trackedProfiles.all(workspaceId) },
        (current) =>
          current?.map((item) => (item.id === updated.id ? updated : item)),
      );
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
