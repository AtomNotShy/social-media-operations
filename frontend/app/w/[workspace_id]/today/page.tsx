import type { Metadata } from "next";
import { TodayPage } from "@/src/features/production/today-page";
export const metadata: Metadata = { title: "今日" };
export default async function Page({ params }: { params: Promise<{ workspace_id: string }> }) { const { workspace_id } = await params; return <TodayPage workspaceId={workspace_id} />; }
