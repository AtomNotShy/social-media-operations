import type { Metadata } from "next";
import { ExperimentsPage } from "@/src/features/production/experiments-page";
export const metadata: Metadata = { title: "运营实验" };
export default async function Page({ params }: { params: Promise<{ workspace_id: string }> }) { const { workspace_id } = await params; return <ExperimentsPage workspaceId={workspace_id} />; }
