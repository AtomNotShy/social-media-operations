import type { Metadata } from "next";
import { SchedulePage } from "@/src/features/production/schedule-page";
export const metadata: Metadata = { title: "内容排期" };
export default async function Page({ params }: { params: Promise<{ workspace_id: string }> }) { const { workspace_id } = await params; return <SchedulePage workspaceId={workspace_id} />; }
