import type { Metadata } from "next";
import { InspirationsPage } from "@/src/features/inspirations/inspirations-page";

export const metadata: Metadata = { title: "灵感库" };

export default async function Page({
  params,
}: {
  params: Promise<{ workspace_id: string }>;
}) {
  const { workspace_id: workspaceId } = await params;
  return <InspirationsPage workspaceId={workspaceId} />;
}
