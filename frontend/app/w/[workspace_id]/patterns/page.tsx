import type { Metadata } from "next";
import { PatternsPage } from "@/src/features/patterns/patterns-page";

export const metadata: Metadata = { title: "可复用模式" };

export default async function Page({
  params,
}: {
  params: Promise<{ workspace_id: string }>;
}) {
  const { workspace_id: workspaceId } = await params;
  return <PatternsPage workspaceId={workspaceId} />;
}
