import type { Metadata } from "next";
import { JobsPage } from "@/src/features/jobs/jobs-page";

export const metadata: Metadata = { title: "任务中心" };

export default async function Page({
  params,
}: {
  params: Promise<{ workspace_id: string }>;
}) {
  const { workspace_id: workspaceId } = await params;
  return <JobsPage workspaceId={workspaceId} />;
}
