import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { DevLoginPage } from "@/src/features/identity/dev-login-page";

export const metadata: Metadata = { title: "开发登录" };

export default function LoginPage() {
  if (process.env.NODE_ENV === "production") {
    redirect("/w/demo/today");
  }
  return <DevLoginPage />;
}
