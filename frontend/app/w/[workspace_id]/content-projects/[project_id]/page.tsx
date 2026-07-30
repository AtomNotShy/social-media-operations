import type { Metadata } from "next";
import { ProjectDetailPage } from "@/src/features/production/project-detail-page";
export const metadata: Metadata = { title: "项目详情" };
export default async function Page({ params }: { params: Promise<{ workspace_id: string; project_id: string }> }) { const { workspace_id, project_id } = await params; return <ProjectDetailPage workspaceId={workspace_id} projectId={project_id} />; }
