import type { Metadata } from "next";
import { UsagePage } from "@/src/features/usage/usage-page";

export const metadata: Metadata = { title: "用量与费用" };

export default async function Page({
  params,
}: {
  params: Promise<{ workspace_id: string }>;
}) {
  const { workspace_id: workspaceId } = await params;
  return <UsagePage workspaceId={workspaceId} />;
}
