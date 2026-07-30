import type { Metadata } from "next";
import { BellRing, Database, ShieldCheck } from "lucide-react";
import { PageHeader } from "@/src/components/ui/page-header";

export const metadata: Metadata = { title: "工作区设置" };

export default function SettingsPage() {
  return (
    <>
      <PageHeader
        eyebrow="系统"
        title="工作区设置"
        description="管理数据连接、通知与成员权限。P0 先展示系统边界，后续配置按后端能力逐项开放。"
      />
      <div className="grid gap-4 lg:grid-cols-3">
        {[
          {
            icon: Database,
            title: "数据连接",
            text: "TikHub 凭据只保存在后端，浏览器不会接触供应商密钥。",
            status: "后端托管",
          },
          {
            icon: BellRing,
            title: "任务通知",
            text: "同步失败与需要人工处理的任务会留在任务中心。",
            status: "规划中",
          },
          {
            icon: ShieldCheck,
            title: "成员权限",
            text: "Owner、Editor 与 Viewer 采用工作区级权限控制。",
            status: "P0",
          },
        ].map((item) => (
          <section
            className="rounded-xl border border-border bg-surface p-5 shadow-panel"
            key={item.title}
          >
            <div className="mb-8 flex items-start justify-between">
              <span className="rounded-lg bg-primary-50 p-2.5 text-primary-600">
                <item.icon aria-hidden="true" size={20} />
              </span>
              <span className="rounded-full bg-surface-subtle px-2.5 py-1 text-xs font-medium text-text-muted">
                {item.status}
              </span>
            </div>
            <h2 className="text-base font-semibold">{item.title}</h2>
            <p className="mt-2 text-sm leading-6 text-text-muted">{item.text}</p>
          </section>
        ))}
      </div>
    </>
  );
}
