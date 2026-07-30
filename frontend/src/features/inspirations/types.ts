import type { components } from "@/src/api/generated/schema";

export type Inspiration = components["schemas"]["InspirationRead"];
export type InspirationUpdate = components["schemas"]["InspirationUpdate"];
export type ExternalContent = components["schemas"]["ExternalContentRead"];
export type ContentScore = components["schemas"]["ContentScoreRead"];
export type ContentMetricSnapshot =
  components["schemas"]["ContentMetricSnapshotRead"];
export type CommentSample = components["schemas"]["CommentSampleRead"];
export type AnalysisRun = components["schemas"]["AnalysisRunRead"];
export type Transcript = components["schemas"]["TranscriptRead"];
export type ImportURLRequest = components["schemas"]["ImportURLRequest"];
export type ImportURLResult = components["schemas"]["ImportURLRead"];
export type Topic = components["schemas"]["TopicRead"];
export type TopicFromInspiration =
  components["schemas"]["TopicFromInspiration"];
