import type { Metadata } from "next";
import { Providers } from "@/app/providers";
import "./globals.css";

export const metadata: Metadata = {
  metadataBase: new URL(
    process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000",
  ),
  title: {
    default: "序章 · 社媒运营工作台",
    template: "%s · 序章",
  },
  description: "从对标账号、灵感、选题到发布复盘的一体化社媒运营工作台。",
  openGraph: {
    title: "序章 · 社媒运营工作台",
    description: "从洞察到发布，让内容运营有序发生。",
    images: [{ url: "/og.png", width: 1734, height: 909 }],
    locale: "zh_CN",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "序章 · 社媒运营工作台",
    description: "从洞察到发布，让内容运营有序发生。",
    images: ["/og.png"],
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
