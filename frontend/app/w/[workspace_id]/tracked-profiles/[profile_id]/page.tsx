import type { Metadata } from "next";
import { TrackedProfileDetailPage } from "@/src/features/tracked-profiles/tracked-profile-detail-page";

export const metadata: Metadata = { title: "对标账号详情" };

export default async function Page({
  params,
}: {
  params: Promise<{ workspace_id: string; profile_id: string }>;
}) {
  const { workspace_id: workspaceId, profile_id: profileId } = await params;
  return (
    <TrackedProfileDetailPage
      profileId={profileId}
      workspaceId={workspaceId}
    />
  );
}
