import type { Metadata } from "next";
import { ReviewDetailPage } from "@/src/features/production/review-detail-page";
export const metadata: Metadata = { title: "发布复盘" };
export default async function Page({ params }: { params: Promise<{ workspace_id: string; record_id: string }> }) { const { workspace_id, record_id } = await params; return <ReviewDetailPage workspaceId={workspace_id} recordId={record_id} />; }
