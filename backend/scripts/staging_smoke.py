#!/usr/bin/env python3
import json
import os
import sys
import uuid
from urllib.parse import urlsplit

import httpx


class SmokeFailure(RuntimeError):
    pass


def required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise SmokeFailure(f"{name} is required")
    return value


def expect(
    client: httpx.Client,
    method: str,
    path: str,
    *,
    headers: dict[str, str] | None = None,
    status_code: int = 200,
) -> httpx.Response:
    response = client.request(method, path, headers=headers)
    if response.status_code != status_code:
        raise SmokeFailure(
            f"{method} {path} returned {response.status_code}; expected {status_code}"
        )
    return response


def main() -> int:
    try:
        base_url = required_env("STAGING_BASE_URL").rstrip("/")
        access_token = required_env("STAGING_ACCESS_TOKEN")
        workspace_id = uuid.UUID(required_env("STAGING_WORKSPACE_ID"))
        parsed = urlsplit(base_url)
        if parsed.scheme != "https" or not parsed.hostname:
            raise SmokeFailure("STAGING_BASE_URL must be an HTTPS origin")
        auth = {"Authorization": f"Bearer {access_token}"}
        workspace_headers = {
            **auth,
            "X-Workspace-Id": str(workspace_id),
        }
        checks = []
        with httpx.Client(
            base_url=base_url,
            timeout=15,
            follow_redirects=False,
        ) as client:
            for path in ("/health/live", "/health/ready"):
                response = expect(client, "GET", path)
                if response.json().get("status") != "ok":
                    raise SmokeFailure(f"{path} did not report ok")
                checks.append(path)

            response = expect(client, "GET", "/api/v1/me", headers=auth)
            if "X-Request-Id" not in response.headers:
                raise SmokeFailure("/api/v1/me did not return X-Request-Id")
            checks.append("/api/v1/me")

            expected_paths = (
                f"/api/v1/workspaces/{workspace_id}",
                "/api/v1/system/queue-health",
                "/api/v1/dashboard/today",
                "/api/v1/search?q=staging-smoke&limit=1",
            )
            for path in expected_paths:
                response = expect(client, "GET", path, headers=workspace_headers)
                if "X-Request-Id" not in response.headers:
                    raise SmokeFailure(f"{path} did not return X-Request-Id")
                checks.append(path.split("?")[0])

            missing_id = uuid.uuid4()
            response = expect(
                client,
                "GET",
                f"/api/v1/workspaces/{missing_id}",
                headers=auth,
                status_code=404,
            )
            if not response.headers.get("content-type", "").startswith("application/problem+json"):
                raise SmokeFailure("404 response is not application/problem+json")
            if response.json().get("code") != "NOT_FOUND":
                raise SmokeFailure("404 response did not preserve stable NOT_FOUND code")
            checks.append("problem-details")

            metrics_token = os.getenv("STAGING_METRICS_BEARER_TOKEN", "").strip()
            if metrics_token:
                response = expect(
                    client,
                    "GET",
                    "/metrics",
                    headers={"Authorization": f"Bearer {metrics_token}"},
                )
                if "social_ops_http_requests_total" not in response.text:
                    raise SmokeFailure("/metrics did not expose Xuzhang HTTP metrics")
                checks.append("/metrics")
        print(
            json.dumps(
                {
                    "status": "passed",
                    "base_url": base_url,
                    "workspace_id": str(workspace_id),
                    "read_only": True,
                    "checks": checks,
                },
                sort_keys=True,
            )
        )
        return 0
    except (SmokeFailure, httpx.HTTPError, ValueError) as exc:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "error": str(exc),
                },
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
