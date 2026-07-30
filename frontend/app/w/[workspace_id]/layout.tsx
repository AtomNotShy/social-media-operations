import { WorkbenchShell } from "@/src/components/workbench/workbench-shell";

export default async function WorkspaceLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ workspace_id: string }>;
}) {
  const { workspace_id: workspaceId } = await params;

  return <WorkbenchShell workspaceId={workspaceId}>{children}</WorkbenchShell>;
}
