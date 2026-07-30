import type { Metadata } from "next";
import { ProjectsPage } from "@/src/features/production/projects-page";
export const metadata: Metadata = { title: "内容项目" };
export default async function Page({ params }: { params: Promise<{ workspace_id: string }> }) { const { workspace_id } = await params; return <ProjectsPage workspaceId={workspace_id} />; }
