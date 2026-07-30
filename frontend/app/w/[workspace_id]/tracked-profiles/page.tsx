import type { Metadata } from "next";
import { TrackedProfilesPage } from "@/src/features/tracked-profiles/tracked-profiles-page";

export const metadata: Metadata = { title: "对标账号" };

export default async function Page({
  params,
}: {
  params: Promise<{ workspace_id: string }>;
}) {
  const { workspace_id: workspaceId } = await params;
  return <TrackedProfilesPage workspaceId={workspaceId} />;
}
