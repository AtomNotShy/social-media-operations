import type { Metadata } from "next";
import { CreateWorkspacePage } from "@/src/features/identity/create-workspace-page";

export const metadata: Metadata = { title: "创建工作区" };

export default function NewWorkspacePage() {
  return <CreateWorkspacePage />;
}
