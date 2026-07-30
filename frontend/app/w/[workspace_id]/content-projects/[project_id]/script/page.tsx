import type { Metadata } from "next";
import { ScriptPage } from "@/src/features/production/script-page";
export const metadata: Metadata = { title: "脚本工作台" };
export default async function Page({ params }: { params: Promise<{ workspace_id: string; project_id: string }> }) { const { workspace_id, project_id } = await params; return <ScriptPage workspaceId={workspace_id} projectId={project_id} />; }
