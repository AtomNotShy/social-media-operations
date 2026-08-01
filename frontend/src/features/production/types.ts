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
