import type { Metadata } from "next";
import { TopicsPage } from "@/src/features/production/topics-page";
export const metadata: Metadata = { title: "选题" };
export default async function Page({ params }: { params: Promise<{ workspace_id: string }> }) { const { workspace_id } = await params; return <TopicsPage workspaceId={workspace_id} />; }
