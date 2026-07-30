import type { Metadata } from "next";
import { DevLoginPage } from "@/src/features/identity/dev-login-page";

export const metadata: Metadata = { title: "开发登录" };

export default function LoginPage() {
  return <DevLoginPage />;
}
