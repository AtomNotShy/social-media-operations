import createClient from "openapi-fetch";
import type { paths } from "@/src/api/generated/schema";
import { toAppError } from "@/src/api/errors";

const developmentBuild = process.env.NODE_ENV !== "production";
const apiBaseUrl =
  process.env.NEXT_PUBLIC_API_BASE_URL ??
  (developmentBuild ? "http://127.0.0.1:8000" : "");

const accessTokenStorageKey = "social-ops.dev-access-token.v1";
const defaultDevelopmentAccessToken = developmentBuild
  ? "dev:local-owner"
  : null;
let accessToken: string | null | undefined;

export function getAccessToken(): string | null {
  if (accessToken !== undefined) return accessToken;
  if (typeof window === "undefined") {
    return defaultDevelopmentAccessToken;
  }
  const storedToken = window.sessionStorage.getItem(accessTokenStorageKey);
  accessToken =
    storedToken === null
      ? defaultDevelopmentAccessToken
      : storedToken || null;
  return accessToken;
}

export function setAccessToken(token: string | null) {
  accessToken = token;
  if (typeof window !== "undefined") {
    // An empty value is an explicit signed-out marker. Removing the key would
    // reactivate the local-development default after a full-page reload.
    window.sessionStorage.setItem(accessTokenStorageKey, token ?? "");
  }
}

export const api = createClient<paths>({
  baseUrl: apiBaseUrl,
});

api.use({
  async onRequest({ request }) {
    const token = getAccessToken();
    if (token) {
      request.headers.set("Authorization", `Bearer ${token}`);
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
