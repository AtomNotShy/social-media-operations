"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { queryKeys } from "@/src/api/query-keys";
import * as service from "@/src/features/production/api";
import {
  demoAssets,
  demoChannels,
  demoExperiments,
  demoPerformance,
  demoPlans,
  demoProjects,
  demoRecords,
  demoReviews,
  demoSavedViews,
  demoScripts,
  demoToday,
  demoTopics,
} from "@/src/features/production/fixtures";
import type {
  Asset,
  ContentProject,
  ContentProjectCreate,
  Experiment,
  ExperimentCreate,
  MarkPublished,
  OwnedChannel,
  OwnedChannelCreate,
  PositioningUpdate,
  PublishPlan,
  PublishPlanCreate,
  Review,
  ReviewCreate,
  SavedView,
  SavedViewCreate,
  ScriptCreate,
  ScriptVersion,
  Topic,
  TopicCreate,
  TopicUpdate,
  VideoRun,
} from "@/src/features/production/types";

const clone = <T>(value: T): T => structuredClone(value);
const stamp = () => new Date().toISOString();

export function useChannels(workspaceId: string) {
  return useQuery({
    queryKey: queryKeys.production.channels(workspaceId),
    queryFn: async () => {
      const items =
        workspaceId === "demo"
          ? clone(demoChannels)
          : await service.listChannels(workspaceId);
      return items.filter((item) => item.active);
    },
  });
}

export function useChannel(workspaceId: string, channelId: string) {
  return useQuery({
    queryKey: queryKeys.production.channel(workspaceId, channelId),
    queryFn: async () => {
      if (workspaceId !== "demo")
        return service.getChannel(workspaceId, channelId);
      const channel = clone(demoChannels).find((item) => item.id === channelId);
      if (!channel) throw new Error("没有找到这个自有账号。");
      return channel;
    },
  });
}

export function useCreateChannel(workspaceId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (input: OwnedChannelCreate) => {
      if (workspaceId !== "demo")
        return service.createChannel(workspaceId, input);
      const now = stamp();
      return {
        ...input,
        id: crypto.randomUUID(),
        external_id: input.external_id ?? null,
        handle: input.handle ?? null,
        audience: input.audience ?? {},
        content_pillars: input.content_pillars ?? [],
        tone_rules: input.tone_rules ?? [],
        prohibited_topics: input.prohibited_topics ?? [],
        active: true,
        created_at: now,
        updated_at: now,
      } satisfies OwnedChannel;
    },
    onSuccess: (created) =>
      client.setQueryData<OwnedChannel[]>(
        queryKeys.production.channels(workspaceId),
        (items = clone(demoChannels)) => [created, ...items],
      ),
  });
}

export function useDisableChannel(workspaceId: string, channelId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      if (workspaceId !== "demo") {
        return service.disableChannel(workspaceId, channelId);
      }
      const current =
        client.getQueryData<OwnedChannel>(
          queryKeys.production.channel(workspaceId, channelId),
        ) ?? clone(demoChannels).find((item) => item.id === channelId);
      if (!current) throw new Error("没有找到这个自有账号。");
      return {
        ...current,
        active: false,
        publishing_mode: "disabled",
        updated_at: stamp(),
      } satisfies OwnedChannel;
    },
    onSuccess: (disabled) => {
      client.setQueryData(
        queryKeys.production.channel(workspaceId, channelId),
        disabled,
      );
      client.setQueryData<OwnedChannel[]>(
        queryKeys.production.channels(workspaceId),
        (items = clone(demoChannels)) =>
          items.filter((item) => item.id !== channelId),
      );
    },
  });
}

export function useSavePositioning(workspaceId: string, channelId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (input: PositioningUpdate) => {
      if (workspaceId !== "demo") {
        return service.savePositioning(workspaceId, channelId, input);
      }
      const current =
        client.getQueryData<OwnedChannel>(
          queryKeys.production.channel(workspaceId, channelId),
        ) ?? clone(demoChannels).find((item) => item.id === channelId);
      if (!current) throw new Error("没有找到这个自有账号。");
      return { ...current, ...input, updated_at: stamp() };
    },
    onSuccess: (updated) => {
      client.setQueryData(
        queryKeys.production.channel(workspaceId, channelId),
        updated,
      );
      client.setQueryData<OwnedChannel[]>(
        queryKeys.production.channels(workspaceId),
        (items = clone(demoChannels)) =>
          items.map((item) => (item.id === updated.id ? updated : item)),
      );
    },
  });
}

export function useTopics(workspaceId: string, status?: string) {
  return useQuery({
    queryKey: queryKeys.production.topics(workspaceId, status),
    queryFn: async () => {
      const items =
        workspaceId === "demo"
          ? clone(demoTopics)
          : await service.listTopics(workspaceId, status);
      return status ? items.filter((item) => item.status === status) : items;
    },
  });
}

export function useTopic(workspaceId: string, topicId: string) {
  return useQuery({
    queryKey: queryKeys.production.topic(workspaceId, topicId),
    queryFn: async () => {
      if (workspaceId !== "demo") return service.getTopic(workspaceId, topicId);
      const topic = clone(demoTopics).find((item) => item.id === topicId);
      if (!topic) throw new Error("没有找到这个选题。");
      return topic;
    },
  });
}

export function useCreateTopic(workspaceId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (input: TopicCreate) => {
      if (workspaceId !== "demo")
        return service.createTopic(workspaceId, input);
      const now = stamp();
      return {
        ...input,
        id: crypto.randomUUID(),
        owned_channel_id: input.owned_channel_id ?? null,
        audience_problem: input.audience_problem ?? null,
        angle: input.angle ?? null,
        hook: input.hook ?? null,
        evidence_refs: input.evidence_refs ?? [],
        version: 1,
        created_by: null,
        created_at: now,
        updated_at: now,
      } satisfies Topic;
    },
    onSuccess: () =>
      client.invalidateQueries({
        queryKey: ["workspaces", workspaceId, "topics"],
      }),
  });
}

export function useUpdateTopic(workspaceId: string, topicId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (input: TopicUpdate) => {
      if (workspaceId !== "demo")
        return service.updateTopic(workspaceId, topicId, input);
      const current =
        client.getQueryData<Topic>(
          queryKeys.production.topic(workspaceId, topicId),
        ) ?? clone(demoTopics).find((item) => item.id === topicId);
      if (!current) throw new Error("没有找到这个选题。");
      if (input.version !== current.version)
        throw new Error("选题已被其他成员修改，请刷新。");
      return {
        ...current,
        ...input,
        version: current.version + 1,
        updated_at: stamp(),
      } as Topic;
    },
    onSuccess: (updated) => {
      client.setQueryData(
        queryKeys.production.topic(workspaceId, topicId),
        updated,
      );
      client.invalidateQueries({
        queryKey: ["workspaces", workspaceId, "topics"],
      });
    },
  });
}

export function useBulkUpdateTopics(workspaceId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async ({
      topics,
      status,
    }: {
      topics: Topic[];
      status: "selected" | "rejected" | "archived";
    }) => {
      if (workspaceId === "demo") {
        return topics.map((item) => ({
          ...item,
          status,
          version: item.version + 1,
          updated_at: stamp(),
        }));
      }
      return Promise.all(
        topics.map((item) =>
          service.updateTopic(workspaceId, item.id, {
            version: item.version,
            status,
          }),
        ),
      );
    },
    onSuccess: () =>
      client.invalidateQueries({
        queryKey: ["workspaces", workspaceId, "topics"],
      }),
  });
}

export function useProjects(workspaceId: string, status?: string) {
  return useQuery({
    queryKey: queryKeys.production.projects(workspaceId, status),
    queryFn: async () => {
      const items =
        workspaceId === "demo"
          ? clone(demoProjects)
          : await service.listProjects(workspaceId, status);
      return status ? items.filter((item) => item.status === status) : items;
    },
  });
}

export function useProject(workspaceId: string, projectId: string) {
  return useQuery({
    queryKey: queryKeys.production.project(workspaceId, projectId),
    queryFn: async () => {
      if (workspaceId !== "demo")
        return service.getProject(workspaceId, projectId);
      const project = clone(demoProjects).find((item) => item.id === projectId);
      if (!project) throw new Error("没有找到这个内容项目。");
      return project;
    },
  });
}

export function useCreateProject(workspaceId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (input: ContentProjectCreate) => {
      if (workspaceId !== "demo")
        return service.createProject(workspaceId, input);
      const now = stamp();
      return {
        ...input,
        id: crypto.randomUUID(),
        topic_id: input.topic_id ?? null,
        owner_user_id: input.owner_user_id ?? null,
        due_at: input.due_at ?? null,
        status: "idea",
        version: 1,
        created_at: now,
        updated_at: now,
      } satisfies ContentProject;
    },
    onSuccess: () =>
      client.invalidateQueries({
        queryKey: ["workspaces", workspaceId, "content-projects"],
      }),
  });
}

export function useTransitionProject(workspaceId: string, projectId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async ({
      from,
      to,
      version,
    }: {
      from: string;
      to: string;
      version: number;
    }) => {
      if (workspaceId !== "demo") {
        return service.transitionProject(
          workspaceId,
          projectId,
          from,
          to,
          version,
        );
      }
      const current =
        client.getQueryData<ContentProject>(
          queryKeys.production.project(workspaceId, projectId),
        ) ?? clone(demoProjects).find((item) => item.id === projectId);
      if (!current || current.version !== version || current.status !== from) {
        throw new Error("项目状态已变化，请刷新后重试。");
      }
      return {
        ...current,
        status: to,
        version: version + 1,
        updated_at: stamp(),
      };
    },
    onSuccess: (updated) => {
      client.setQueryData(
        queryKeys.production.project(workspaceId, projectId),
        updated,
      );
      client.invalidateQueries({
        queryKey: ["workspaces", workspaceId, "content-projects"],
      });
    },
  });
}

export function useScripts(workspaceId: string, projectId: string) {
  return useQuery({
    queryKey: queryKeys.production.scripts(workspaceId, projectId),
    queryFn: () =>
      workspaceId === "demo"
        ? clone(demoScripts).filter(
            (item) => item.content_project_id === projectId,
          )
        : service.listScripts(workspaceId, projectId),
  });
}

export function useSaveScript(workspaceId: string, projectId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (input: ScriptCreate) => {
      if (workspaceId !== "demo")
        return service.createScript(workspaceId, projectId, input);
      const existing =
        client.getQueryData<ScriptVersion[]>(
          queryKeys.production.scripts(workspaceId, projectId),
        ) ??
        clone(demoScripts).filter(
          (item) => item.content_project_id === projectId,
        );
      return {
        id: crypto.randomUUID(),
        content_project_id: projectId,
        version_no: Math.max(0, ...existing.map((item) => item.version_no)) + 1,
        body: input.body,
        structured_body: input.structured_body ?? null,
        created_by: null,
        generation_run_id: null,
        change_note: input.change_note ?? null,
        created_at: stamp(),
      } satisfies ScriptVersion;
    },
    onSuccess: (created, variables) => {
      client.setQueryData<ScriptVersion[]>(
        queryKeys.production.scripts(workspaceId, projectId),
        (items = []) => [created, ...items],
      );
      client.setQueryData<ContentProject>(
        queryKeys.production.project(workspaceId, projectId),
        (project) =>
          project
            ? {
                ...project,
                version: variables.project_version + 1,
                status:
                  project.status === "idea" ? "scripting" : project.status,
                updated_at: stamp(),
              }
            : project,
      );
      if (workspaceId !== "demo") {
        client.invalidateQueries({
          queryKey: queryKeys.production.project(workspaceId, projectId),
        });
      }
    },
  });
}

export function useGenerateScript(workspaceId: string, projectId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async ({
      projectVersion,
      instruction,
    }: {
      projectVersion: number;
      instruction?: string;
    }) => {
      if (workspaceId !== "demo") {
        const accepted = await service.generateScript(
          workspaceId,
          projectId,
          projectVersion,
          instruction,
        );
        return {
          jobId: accepted.generation.id,
          status: accepted.generation.status,
          reused: accepted.reused,
        };
      }
      return { jobId: crypto.randomUUID(), status: "pending", reused: false };
    },
    onSuccess: () => {
      client.invalidateQueries({
        queryKey: queryKeys.production.scripts(workspaceId, projectId),
      });
      client.invalidateQueries({ queryKey: queryKeys.jobs.all(workspaceId) });
    },
  });
}

export function useAssets(workspaceId: string, projectId?: string) {
  return useQuery({
    queryKey: queryKeys.production.assets(workspaceId, projectId),
    queryFn: async () => {
      const items =
        workspaceId === "demo"
          ? clone(demoAssets)
          : await service.listAssets(workspaceId, projectId);
      return projectId
        ? items.filter((item) => item.content_project_id === projectId)
        : items;
    },
  });
}

export function useVideoRuns(workspaceId: string, projectId: string) {
  return useQuery({
    queryKey: queryKeys.production.videos(workspaceId, projectId),
    queryFn: () =>
      workspaceId === "demo"
        ? []
        : service.listVideoRuns(workspaceId, projectId),
    refetchInterval: (query) =>
      query.state.data?.some(
        (run) => run.status === "queued" || run.status === "running",
      )
        ? 3000
        : false,
  });
}

export function useRequestVideo(workspaceId: string, projectId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: { scriptVersionId: string }) => {
      if (workspaceId === "demo") {
        return Promise.resolve({
          video_run: { id: crypto.randomUUID(), status: "queued" } as VideoRun,
          reused: false,
        });
      }
      return service.requestVideo(workspaceId, projectId, {
        script_version_id: input.scriptVersionId,
        force: false,
      });
    },
    onSuccess: () =>
      client.invalidateQueries({
        queryKey: queryKeys.production.videos(workspaceId, projectId),
      }),
  });
}

export function useUploadAsset(workspaceId: string, projectId?: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async ({
      file,
      rightsNote,
    }: {
      file: File;
      rightsNote: string;
    }) => {
      const type: "image" | "video" | "audio" | "subtitle" | "document" =
        file.type.startsWith("image/")
          ? "image"
          : file.type.startsWith("video/")
            ? "video"
            : file.type.startsWith("audio/")
              ? "audio"
              : "document";
      if (workspaceId !== "demo") {
        return service.uploadAsset(
          workspaceId,
          file,
          projectId,
          type,
          rightsNote,
        );
      }
      return {
        id: crypto.randomUUID(),
        content_project_id: projectId ?? null,
        asset_type: type,
        storage_key: `demo/${file.name}`,
        mime_type: file.type || "application/octet-stream",
        size_bytes: file.size,
        checksum: "d".repeat(64),
        source_type: "uploaded",
        rights_note: rightsNote || null,
        created_by: null,
        created_at: stamp(),
      } satisfies Asset;
    },
    onSuccess: () =>
      client.invalidateQueries({
        queryKey: ["workspaces", workspaceId, "assets"],
      }),
  });
}

export function usePlans(workspaceId: string, status?: string) {
  return useQuery({
    queryKey: queryKeys.production.plans(workspaceId, status),
    queryFn: async () => {
      const items =
        workspaceId === "demo"
          ? clone(demoPlans)
          : await service.listPlans(workspaceId, status);
      return status ? items.filter((item) => item.status === status) : items;
    },
  });
}

export function useCreatePlan(workspaceId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (input: PublishPlanCreate) => {
      if (workspaceId !== "demo") return service.createPlan(workspaceId, input);
      const now = stamp();
      return {
        ...input,
        id: crypto.randomUUID(),
        status: "draft",
        approved_by: null,
        approved_at: null,
        version: 1,
        created_at: now,
        updated_at: now,
      } satisfies PublishPlan;
    },
    onSuccess: (created) => {
      client.setQueriesData<PublishPlan[]>(
        { queryKey: ["workspaces", workspaceId, "publish-plans"] },
        (items = clone(demoPlans)) => [...items, created],
      );
      if (workspaceId !== "demo") {
        client.invalidateQueries({
          queryKey: ["workspaces", workspaceId, "publish-plans"],
        });
      }
    },
  });
}

export function usePlanActions(workspaceId: string) {
  const client = useQueryClient();
  return {
    approve: useMutation({
      mutationFn: async (plan: PublishPlan) => {
        if (workspaceId !== "demo")
          return service.approvePlan(workspaceId, plan.id);
        return {
          ...plan,
          status: "approved",
          approved_at: stamp(),
          version: plan.version + 1,
        };
      },
      onSuccess: (updated) => {
        client.setQueriesData<PublishPlan[]>(
          { queryKey: ["workspaces", workspaceId, "publish-plans"] },
          (items = clone(demoPlans)) =>
            items.map((item) => (item.id === updated.id ? updated : item)),
        );
        if (workspaceId !== "demo") {
          client.invalidateQueries({
            queryKey: ["workspaces", workspaceId, "publish-plans"],
          });
        }
      },
    }),
    package: useMutation({
      mutationFn: async (plan: PublishPlan) => {
        if (workspaceId !== "demo")
          return service.buildPackage(workspaceId, plan.id);
        const script =
          clone(demoScripts).find(
            (item) => item.content_project_id === plan.content_project_id,
          ) ?? clone(demoScripts)[0];
        return {
          plan_id: plan.id,
          plan_version: plan.version + 1,
          project_id: plan.content_project_id,
          channel_id: plan.owned_channel_id,
          scheduled_at: plan.scheduled_at,
          payload: plan.publish_payload,
          latest_script: script,
          assets: clone(demoAssets).filter(
            (item) => item.content_project_id === plan.content_project_id,
          ),
          publishing_mode: "manual" as const,
        };
      },
    }),
    mark: useMutation({
      mutationFn: async ({
        plan,
        input,
      }: {
        plan: PublishPlan;
        input: MarkPublished;
      }) => {
        if (workspaceId !== "demo")
          return service.markPublished(workspaceId, plan.id, input);
        return {
          id: crypto.randomUUID(),
          publish_plan_id: plan.id,
          platform_content_id: input.platform_content_id ?? null,
          published_url: input.published_url,
          published_at: input.published_at,
          result_payload: {
            matched_publish_package: input.matched_publish_package,
          },
          created_by: null,
          created_at: stamp(),
        };
      },
      onSuccess: (record, variables) => {
        client.setQueriesData<PublishPlan[]>(
          { queryKey: ["workspaces", workspaceId, "publish-plans"] },
          (items = clone(demoPlans)) =>
            items.map((item) =>
              item.id === variables.plan.id
                ? { ...item, status: "published", version: item.version + 1 }
                : item,
            ),
        );
        if (workspaceId !== "demo") {
          client.invalidateQueries({
            queryKey: ["workspaces", workspaceId, "publish-plans"],
          });
        }
        client.invalidateQueries({
          queryKey: ["workspaces", workspaceId, "dashboard"],
        });
        client.setQueryData(
          ["workspaces", workspaceId, "publish-records", record.id],
          record,
        );
      },
    }),
  };
}

export function useToday(workspaceId: string) {
  return useQuery({
    queryKey: queryKeys.production.today(workspaceId),
    queryFn: () =>
      workspaceId === "demo" ? clone(demoToday) : service.getToday(workspaceId),
  });
}

export function usePerformance(workspaceId: string, days = 30) {
  return useQuery({
    queryKey: queryKeys.production.performance(workspaceId, days),
    queryFn: () => {
      if (workspaceId !== "demo")
        return service.getPerformance(workspaceId, days);
      const source = clone(demoPerformance);
      const fromAt = Date.now() - days * 86_400_000;
      const records = source.records.filter(
        (item) => new Date(item.published_at).getTime() >= fromAt,
      );
      return {
        ...source,
        from_at: new Date(fromAt).toISOString(),
        records,
        totals: {
          published_count: records.length,
          review_count: records.filter((item) => item.latest_review_window)
            .length,
          exposure: records.reduce((sum, item) => sum + item.exposure, 0),
          interactions: records.reduce(
            (sum, item) => sum + item.interactions,
            0,
          ),
          conversions: records.reduce((sum, item) => sum + item.conversions, 0),
        },
      };
    },
  });
}

export function useRecordReviews(workspaceId: string, recordId: string) {
  return useQuery({
    queryKey: queryKeys.production.reviews(workspaceId, recordId),
    queryFn: () =>
      workspaceId === "demo"
        ? clone(demoReviews).filter(
            (item) => item.publish_record_id === recordId,
          )
        : service.listReviews(workspaceId, recordId),
  });
}

export function usePublishRecord(workspaceId: string, recordId: string) {
  return useQuery({
    queryKey: ["workspaces", workspaceId, "publish-records", recordId],
    queryFn: async () => {
      if (workspaceId !== "demo")
        return service.getRecord(workspaceId, recordId);
      const record = clone(demoRecords).find((item) => item.id === recordId);
      if (!record) throw new Error("没有找到这条发布记录。");
      return record;
    },
  });
}

export function useCreateReview(workspaceId: string, recordId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (input: ReviewCreate) => {
      if (workspaceId !== "demo")
        return service.createReview(workspaceId, recordId, input);
      return {
        id: crypto.randomUUID(),
        publish_record_id: recordId,
        review_window: input.review_window,
        metrics: input.metrics,
        analysis: input.analysis ?? {},
        next_actions: input.next_actions ?? [],
        created_by: null,
        created_at: stamp(),
      } satisfies Review;
    },
    onSuccess: (created) =>
      client.setQueryData<Review[]>(
        queryKeys.production.reviews(workspaceId, recordId),
        (items = []) => [created, ...items],
      ),
  });
}

export function useSavedViews(workspaceId: string, entityType: string) {
  return useQuery({
    queryKey: queryKeys.production.savedViews(workspaceId, entityType),
    queryFn: async () => {
      const items =
        workspaceId === "demo"
          ? clone(demoSavedViews)
          : await service.listSavedViews(workspaceId, entityType);
      return items.filter((item) => item.entity_type === entityType);
    },
  });
}

export function useCreateSavedView(workspaceId: string, entityType: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (input: SavedViewCreate) => {
      if (workspaceId !== "demo")
        return service.createSavedView(workspaceId, input);
      const now = stamp();
      return {
        ...input,
        id: crypto.randomUUID(),
        query_params: input.query_params ?? {},
        user_id: "6fd367fb-88b5-4e9c-91d0-bb850ef79001",
        version: 1,
        created_at: now,
        updated_at: now,
      } satisfies SavedView;
    },
    onSuccess: (created) =>
      client.setQueryData<SavedView[]>(
        queryKeys.production.savedViews(workspaceId, entityType),
        (items = []) => [...items, created],
      ),
  });
}

export function useUnifiedSearch(workspaceId: string, query: string) {
  return useQuery({
    queryKey: queryKeys.production.search(workspaceId, query),
    enabled: query.trim().length >= 2,
    queryFn: async () => {
      if (workspaceId !== "demo")
        return service.unifiedSearch(workspaceId, query);
      const needle = query.trim().toLowerCase();
      return [
        ...demoTopics.map((item) => ({
          entity_type: "topic" as const,
          entity_id: item.id,
          title: item.title,
          snippet: item.angle,
          matched_fields: ["title"],
          source_ref: `/api/v1/topics/${item.id}`,
          updated_at: item.updated_at,
        })),
        ...demoProjects.map((item) => ({
          entity_type: "content_project" as const,
          entity_id: item.id,
          title: item.title,
          snippet: `项目状态：${item.status}`,
          matched_fields: ["title"],
          source_ref: `/api/v1/content-projects/${item.id}`,
          updated_at: item.updated_at,
        })),
      ].filter((item) =>
        [item.title, item.snippet].some((text) =>
          text?.toLowerCase().includes(needle),
        ),
      );
    },
    staleTime: 15_000,
  });
}

export function useExperiments(workspaceId: string) {
  return useQuery({
    queryKey: queryKeys.production.experiments(workspaceId),
    queryFn: () =>
      workspaceId === "demo"
        ? clone(demoExperiments)
        : service.listExperiments(workspaceId),
  });
}

export function useCreateExperiment(workspaceId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (input: ExperimentCreate) => {
      if (workspaceId !== "demo")
        return service.createExperiment(workspaceId, input);
      const now = stamp();
      return {
        ...input,
        id: crypto.randomUUID(),
        owned_channel_id: input.owned_channel_id ?? null,
        status: "draft",
        version: 1,
        created_by: null,
        started_at: null,
        ended_at: null,
        created_at: now,
        updated_at: now,
      } satisfies Experiment;
    },
    onSuccess: (created) =>
      client.setQueryData<Experiment[]>(
        queryKeys.production.experiments(workspaceId),
        (items = clone(demoExperiments)) => [created, ...items],
      ),
  });
}

export const demoPublishedRecords = demoRecords;
