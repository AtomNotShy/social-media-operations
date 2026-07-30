import type { Metadata } from "next";
import { ChannelsPage } from "@/src/features/production/channels-page";
export const metadata: Metadata = { title: "自有账号" };
export default async function Page({ params }: { params: Promise<{ workspace_id: string }> }) { const { workspace_id } = await params; return <ChannelsPage workspaceId={workspace_id} />; }
