import type { Metadata } from "next";
import { PatternDetailPage } from "@/src/features/patterns/pattern-detail-page";

export const metadata: Metadata = { title: "模式详情" };

export default async function Page({
  params,
}: {
  params: Promise<{ workspace_id: string; pattern_id: string }>;
}) {
  const { workspace_id: workspaceId, pattern_id: patternId } = await params;
  return <PatternDetailPage patternId={patternId} workspaceId={workspaceId} />;
}
