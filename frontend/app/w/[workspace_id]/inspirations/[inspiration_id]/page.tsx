import type { Metadata } from "next";
import { InspirationDetailPage } from "@/src/features/inspirations/inspiration-detail-page";

export const metadata: Metadata = { title: "灵感详情" };

export default async function Page({
  params,
}: {
  params: Promise<{ workspace_id: string; inspiration_id: string }>;
}) {
  const {
    workspace_id: workspaceId,
    inspiration_id: inspirationId,
  } = await params;
  return (
    <InspirationDetailPage
      inspirationId={inspirationId}
      workspaceId={workspaceId}
    />
  );
}
