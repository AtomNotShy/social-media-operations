import type { Metadata } from "next";
import { DiscoveryPage } from "@/src/features/discovery/discovery-page";

export const metadata: Metadata = { title: "搜索与热榜" };

export default async function Page({
  params,
}: {
  params: Promise<{ workspace_id: string }>;
}) {
  const { workspace_id: workspaceId } = await params;
  return <DiscoveryPage workspaceId={workspaceId} />;
}
