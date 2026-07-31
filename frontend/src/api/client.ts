import createClient from "openapi-fetch";
import type { paths } from "@/src/api/generated/schema";
import { toAppError } from "@/src/api/errors";

const developmentBuild = process.env.NODE_ENV !== "production";
const apiBaseUrl =
  process.env.NEXT_PUBLIC_API_BASE_URL ??
  (developmentBuild ? "http://127.0.0.1:8000" : "");

let accessToken: string | null = developmentBuild
  ? "dev:frontend-owner"
  : null;

export function setAccessToken(token: string | null) {
  accessToken = token;
}

export const api = createClient<paths>({
  baseUrl: apiBaseUrl,
});

api.use({
  async onRequest({ request }) {
    if (accessToken) {
      request.headers.set("Authorization", `Bearer ${accessToken}`);
    } else {
      request.headers.delete("Authorization");
    }
    request.headers.set("X-Request-Id", crypto.randomUUID());
    return request;
  },
  async onResponse({ response }) {
    if (!response.ok) throw await toAppError(response.clone());
    return response;
  },
});

export function workspaceHeaders(workspaceId: string) {
  return { "X-Workspace-Id": workspaceId };
}
