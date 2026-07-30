import type { Metadata } from "next";
import { AssetsPage } from "@/src/features/production/assets-page";
export const metadata: Metadata = { title: "素材库" };
export default async function Page({ params }: { params: Promise<{ workspace_id: string }> }) { const { workspace_id } = await params; return <AssetsPage workspaceId={workspace_id} />; }
