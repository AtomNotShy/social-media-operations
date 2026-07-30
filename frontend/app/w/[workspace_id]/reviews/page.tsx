import type { Metadata } from "next";
import { ReviewsPage } from "@/src/features/production/reviews-page";
export const metadata: Metadata = { title: "复盘" };
export default async function Page({ params }: { params: Promise<{ workspace_id: string }> }) { const { workspace_id } = await params; return <ReviewsPage workspaceId={workspace_id} />; }
