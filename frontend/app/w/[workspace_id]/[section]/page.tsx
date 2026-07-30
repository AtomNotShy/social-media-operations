import { SearchX } from "lucide-react";
import { PageHeader } from "@/src/components/ui/page-header";

export default async function PlannedPage({
  params,
}: {
  params: Promise<{ section: string }>;
}) {
  const { section } = await params;
  return (
    <>
      <PageHeader
        eyebrow="未找到"
        title="页面不存在"
        description={`工作区没有名为“${section}”的功能路由。`}
      />
      <section className="flex min-h-80 flex-col items-center justify-center rounded-xl border border-dashed border-border bg-surface/70 px-6 text-center">
        <span className="mb-4 rounded-xl bg-primary-50 p-3 text-primary-600">
          <SearchX aria-hidden="true" size={24} />
        </span>
        <h2 className="text-lg font-semibold">请检查地址</h2>
        <p className="mt-2 max-w-md text-sm leading-6 text-text-muted">
          已规划功能均使用独立路由；这个通用页面只处理未知地址。
        </p>
      </section>
    </>
  );
}
