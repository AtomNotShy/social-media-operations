import type { Metadata } from "next";
import { SettingsPage } from "@/src/features/settings/settings-page";

export const metadata: Metadata = { title: "工作区设置" };

export default async function Page({
  params,
}: {
  params: Promise<{ workspace_id: string }>;
}) {
  const { workspace_id: workspaceId } = await params;
  return <SettingsPage workspaceId={workspaceId} />;
}
