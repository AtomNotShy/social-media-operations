def test_live_health_does_not_require_auth(client):
    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["X-Request-Id"]


def test_ready_checks_database(client):
    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json()["dependencies"]["database"] == "ok"


def test_dependency_health_is_protected_and_workspace_scoped(
    client,
    auth_headers,
    workspace,
):
    assert client.get("/health/dependencies").status_code == 401

    response = client.get(
        "/health/dependencies",
        headers={**auth_headers, "X-Workspace-Id": workspace["id"]},
    )

    assert response.status_code == 200
    assert response.json()["data"]["database"] == "ok"
    assert response.json()["data"]["queue"]["active_count"] == 0
