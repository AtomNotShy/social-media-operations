import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { localDevelopmentEnabled } from "@/src/config/runtime";
import { DevLoginPage } from "@/src/features/identity/dev-login-page";

export const metadata: Metadata = { title: "开发登录" };

export default function LoginPage() {
  if (!localDevelopmentEnabled) {
    redirect("/w/demo/today");
  }
  return <DevLoginPage />;
}
