import type { Metadata } from "next";
import { TopicDetailPage } from "@/src/features/production/topic-detail-page";
export const metadata: Metadata = { title: "选题详情" };
export default async function Page({ params }: { params: Promise<{ workspace_id: string; topic_id: string }> }) { const { workspace_id, topic_id } = await params; return <TopicDetailPage workspaceId={workspace_id} topicId={topic_id} />; }
