import createClient from "openapi-fetch";
import type { paths } from "@/src/api/generated/schema";
import { toAppError } from "@/src/api/errors";

const apiBaseUrl =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

let accessToken = "dev:frontend-owner";

export function setAccessToken(token: string) {
  accessToken = token;
}

export const api = createClient<paths>({
  baseUrl: apiBaseUrl,
});

api.use({
  async onRequest({ request }) {
    request.headers.set("Authorization", `Bearer ${accessToken}`);
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
