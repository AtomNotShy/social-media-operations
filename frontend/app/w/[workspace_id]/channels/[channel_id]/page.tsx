import type { Metadata } from "next";
import { ChannelDetailPage } from "@/src/features/production/channel-detail-page";
export const metadata: Metadata = { title: "账号定位" };
export default async function Page({ params }: { params: Promise<{ workspace_id: string; channel_id: string }> }) { const { workspace_id, channel_id } = await params; return <ChannelDetailPage workspaceId={workspace_id} channelId={channel_id} />; }
