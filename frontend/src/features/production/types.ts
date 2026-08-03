import type { components } from "@/src/api/generated/schema";

export type OwnedChannel = components["schemas"]["OwnedChannelRead"];
export type OwnedChannelCreate = components["schemas"]["OwnedChannelCreate"];
export type PositioningUpdate = components["schemas"]["PositioningUpdate"];
export type Topic = components["schemas"]["TopicRead"];
export type TopicCreate = components["schemas"]["TopicCreate"];
export type TopicUpdate = components["schemas"]["TopicUpdate"];
export type ContentProject = components["schemas"]["ContentProjectRead"];
export type ContentProjectCreate =
  components["schemas"]["ContentProjectCreate"];
export type ContentProjectUpdate =
  components["schemas"]["ContentProjectUpdate"];
export type ScriptVersion = components["schemas"]["ScriptVersionRead"];
export type ScriptCreate = components["schemas"]["ScriptCreate"];
export type ContentPackage = components["schemas"]["ContentPackageRead"];
export type ContentPackageEdit = components["schemas"]["ContentPackageEdit"];
export type ContentPackageGenerateInput =
  components["schemas"]["ContentPackageGenerateRequest"];
export type ContentPackageScene = components["schemas"]["ContentPackageScene"];
export type ContentPackageTitleCandidate =
  components["schemas"]["ContentPackageTitleCandidate"];

export type ContentPackagePayload = {
  schema_version: number;
  target_platform: string;
  content_type: string;
  target_duration_seconds: number;
  narration: {
    full_text: string;
    spoken_length_chars: number;
    estimated_duration_seconds: number;
  };
  scenes: ContentPackageScene[];
  title_candidates: ContentPackageTitleCandidate[];
  cover: {
    headline: string;
    subheadline: string | null;
    visual_hint: string | null;
  };
  hashtags: string[];
  publish_caption: string;
  assets_required: Array<{
    kind: string;
    query: string;
    source_hint: string | null;
    rights_note: string | null;
  }>;
  audio: {
    voice_hint: string;
    music_mood: string | null;
    music_ducking: string | null;
  };
  publish_timing_hint: string | null;
  evidence_refs: string[];
};

export type Asset = components["schemas"]["AssetRead"];
export type VideoRun = components["schemas"]["VideoRunRead"];
export type VideoRunCreate = components["schemas"]["VideoRunCreate"];
export type PublishPlan = components["schemas"]["PublishPlanRead"];
export type PublishPlanCreate = components["schemas"]["PublishPlanCreate"];
export type PublishPlanUpdate = components["schemas"]["PublishPlanUpdate"];
export type PublishPackage = components["schemas"]["PublishPackage"];
export type PublishRecord = components["schemas"]["PublishRecordRead"];
export type MarkPublished = components["schemas"]["MarkPublishedRequest"];
export type Review = components["schemas"]["ReviewInsightRead"];
export type ReviewCreate = components["schemas"]["ReviewCreate"];
export type TodayDashboard = components["schemas"]["TodayDashboardRead"];
export type PerformanceDashboard =
  components["schemas"]["PerformanceDashboardRead"];
export type SavedView = components["schemas"]["SavedViewRead"];
export type SavedViewCreate = components["schemas"]["SavedViewCreate"];
export type SearchResult = components["schemas"]["UnifiedSearchResult"];
export type Experiment = components["schemas"]["ExperimentRead"];
export type ExperimentCreate = components["schemas"]["ExperimentCreate"];
export type ExperimentResult = components["schemas"]["ExperimentResultsRead"];
