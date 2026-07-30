from datetime import datetime, timezone


def _headers(auth_headers, workspace):
    return {**auth_headers, "X-Workspace-Id": workspace["id"]}


def _channel_and_project(client, headers):
    channel = client.post(
        "/api/v1/owned-channels",
        headers=headers,
        json={
            "platform": "xiaohongshu",
            "display_name": "Experiment channel",
        },
    ).json()["data"]
    project = client.post(
        "/api/v1/content-projects",
        headers=headers,
        json={
            "owned_channel_id": channel["id"],
            "title": "Experiment project",
        },
    ).json()["data"]
    return channel, project


def test_saved_view_versioning_and_workspace_isolation(client, auth_headers, workspace):
    headers = _headers(auth_headers, workspace)
    created = client.post(
        "/api/v1/saved-views",
        headers=headers,
        json={
            "entity_type": "inspirations",
            "name": "High value",
            "query_params": {"grade": ["t1", "t2"]},
            "is_shared": True,
        },
    )
    assert created.status_code == 201
    view = created.json()["data"]

    updated = client.patch(
        f"/api/v1/saved-views/{view['id']}",
        headers=headers,
        json={
            "version": view["version"],
            "query_params": {"grade": ["t1"], "platform": "xiaohongshu"},
        },
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["version"] == 2

    stale = client.patch(
        f"/api/v1/saved-views/{view['id']}",
        headers=headers,
        json={"version": 1, "name": "Stale overwrite"},
    )
    assert stale.status_code == 409

    other_workspace = client.post(
        "/api/v1/workspaces",
        headers=auth_headers,
        json={"name": "Other workspace", "timezone": "UTC"},
    ).json()["data"]
    isolated = client.get(
        "/api/v1/saved-views",
        headers=_headers(auth_headers, other_workspace),
    )
    assert isolated.json()["data"] == []


def test_experiment_assignments_idempotent_events_and_evidence_results(
    client,
    auth_headers,
    workspace,
):
    headers = _headers(auth_headers, workspace)
    channel, project = _channel_and_project(client, headers)
    created = client.post(
        "/api/v1/experiments",
        headers=headers,
        json={
            "owned_channel_id": channel["id"],
            "name": "Hook test",
            "hypothesis": "A direct pain hook increases qualified leads.",
            "primary_metric": "qualified_leads",
            "variants": [
                {"key": "control", "name": "Control"},
                {"key": "pain_hook", "name": "Pain hook"},
            ],
        },
    )
    assert created.status_code == 201
    experiment = created.json()["data"]

    assignment = client.post(
        f"/api/v1/experiments/{experiment['id']}/assignments",
        headers=headers,
        json={
            "content_project_id": project["id"],
            "variant_key": "pain_hook",
        },
    )
    assert assignment.status_code == 201
    assignment_data = assignment.json()["data"]

    started = client.patch(
        f"/api/v1/experiments/{experiment['id']}",
        headers=headers,
        json={"version": experiment["version"], "status": "running"},
    )
    assert started.status_code == 200
    assert started.json()["data"]["started_at"] is not None

    event_body = {
        "assignment_id": assignment_data["id"],
        "event_type": "conversion",
        "metric_name": "qualified_leads",
        "value": "3",
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "source": "analytics",
        "source_ref": "analytics://campaign/hook-test/day-1",
        "idempotency_key": "hook-test-day-1-qualified-leads",
        "metadata": {"window": "24h"},
    }
    first = client.post(
        f"/api/v1/experiments/{experiment['id']}/events",
        headers=headers,
        json=event_body,
    )
    second = client.post(
        f"/api/v1/experiments/{experiment['id']}/events",
        headers=headers,
        json=event_body,
    )
    assert first.status_code == 201
    assert first.json()["data"]["id"] == second.json()["data"]["id"]

    conflict = client.post(
        f"/api/v1/experiments/{experiment['id']}/events",
        headers=headers,
        json={**event_body, "value": "4"},
    )
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "IDEMPOTENCY_KEY_REUSED"

    results = client.get(
        f"/api/v1/experiments/{experiment['id']}/results",
        headers=headers,
    )
    assert results.status_code == 200
    result = results.json()["data"]
    assert result["experiment_version"] == 2
    by_key = {item["variant_key"]: item for item in result["variants"]}
    assert by_key["control"]["total_value"] == "0"
    assert by_key["pain_hook"]["assignment_count"] == 1
    assert by_key["pain_hook"]["event_count"] == 1
    assert by_key["pain_hook"]["total_value"] == "3.000000"
    assert by_key["pain_hook"]["evidence_event_ids"] == [first.json()["data"]["id"]]
    assert by_key["pain_hook"]["source_refs"] == ["analytics://campaign/hook-test/day-1"]
