import type { Metadata } from "next";
import { AssetsPage } from "@/src/features/production/assets-page";
export const metadata: Metadata = { title: "项目素材" };
export default async function Page({ params }: { params: Promise<{ workspace_id: string; project_id: string }> }) { const { workspace_id, project_id } = await params; return <AssetsPage workspaceId={workspace_id} projectId={project_id} />; }
