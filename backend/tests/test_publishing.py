from datetime import datetime, timedelta, timezone


def _headers(auth_headers, workspace):
    return {**auth_headers, "X-Workspace-Id": workspace["id"]}


def _ready_project(client, headers):
    channel = client.post(
        "/api/v1/owned-channels",
        headers=headers,
        json={
            "platform": "xiaohongshu",
            "display_name": "发布测试账号",
        },
    ).json()["data"]
    project = client.post(
        "/api/v1/content-projects",
        headers=headers,
        json={
            "owned_channel_id": channel["id"],
            "title": "发布测试项目",
        },
    ).json()["data"]
    client.post(
        f"/api/v1/content-projects/{project['id']}/scripts",
        headers=headers,
        json={
            "project_version": 1,
            "body": "这是经过审核的发布脚本。",
        },
    )
    producing = client.post(
        f"/api/v1/content-projects/{project['id']}/transition",
        headers=headers,
        json={"from": "scripting", "to": "producing", "version": 2},
    ).json()["data"]
    reviewed = client.post(
        f"/api/v1/content-projects/{project['id']}/transition",
        headers=headers,
        json={"from": "producing", "to": "review", "version": producing["version"]},
    ).json()["data"]
    return channel, reviewed


def test_manual_publish_package_record_and_review_flow(
    client,
    auth_headers,
    workspace,
):
    headers = _headers(auth_headers, workspace)
    channel, project = _ready_project(client, headers)
    scheduled_at = datetime.now(timezone.utc) + timedelta(days=1)
    plan = client.post(
        "/api/v1/publish-plans",
        headers=headers,
        json={
            "content_project_id": project["id"],
            "owned_channel_id": channel["id"],
            "scheduled_at": scheduled_at.isoformat(),
            "publishing_mode": "manual",
            "publish_payload": {
                "title": "高峰期如何减少漏单",
                "topics": ["餐饮运营"],
            },
        },
    )
    assert plan.status_code == 201
    plan_data = plan.json()["data"]
    assert plan_data["status"] == "draft"

    approved = client.post(
        f"/api/v1/publish-plans/{plan_data['id']}/approve",
        headers=headers,
    )
    assert approved.status_code == 200
    assert approved.json()["data"]["status"] == "approved"
    assert approved.json()["data"]["version"] == 2

    package = client.post(
        f"/api/v1/publish-plans/{plan_data['id']}/publish",
        headers=headers,
    )
    assert package.status_code == 200
    package_data = package.json()["data"]
    assert package_data["publishing_mode"] == "manual"
    assert package_data["latest_script"]["body"] == "这是经过审核的发布脚本。"
    assert package_data["plan_version"] == 3

    invalid_url = client.post(
        f"/api/v1/publish-plans/{plan_data['id']}/mark-published",
        headers=headers,
        json={
            "version": package_data["plan_version"],
            "published_url": "http://127.0.0.1/private",
            "published_at": datetime.now(timezone.utc).isoformat(),
            "matched_publish_package": True,
        },
    )
    assert invalid_url.status_code == 422

    published = client.post(
        f"/api/v1/publish-plans/{plan_data['id']}/mark-published",
        headers=headers,
        json={
            "version": package_data["plan_version"],
            "published_url": "https://www.xiaohongshu.com/explore/published-fixture",
            "published_at": datetime.now(timezone.utc).isoformat(),
            "platform_content_id": "published-fixture",
            "matched_publish_package": True,
        },
    )
    assert published.status_code == 201
    record = published.json()["data"]
    assert record["result_payload"]["matched_publish_package"] is True
    project_after = client.get(
        f"/api/v1/content-projects/{project['id']}",
        headers=headers,
    ).json()["data"]
    assert project_after["status"] == "published"

    review = client.post(
        f"/api/v1/publish-records/{record['id']}/reviews",
        headers=headers,
        json={
            "review_window": "24h",
            "metrics": {"views": 1200, "likes": 88},
            "analysis": {"hypothesis": "痛点钩子有效"},
            "next_actions": ["复测同类钩子"],
        },
    )
    assert review.status_code == 201
    assert review.json()["data"]["review_window"] == "24h"
    project_reviewing = client.get(
        f"/api/v1/content-projects/{project['id']}",
        headers=headers,
    ).json()["data"]
    assert project_reviewing["status"] == "reviewing"

    performance = client.get("/api/v1/dashboard/performance", headers=headers)
    assert performance.status_code == 200
    totals = performance.json()["data"]["totals"]
    assert totals == {
        "published_count": 1,
        "review_count": 1,
        "exposure": 1200,
        "interactions": 88,
        "conversions": 0,
    }
    assert performance.json()["data"]["records"][0]["latest_review_window"] == "24h"
    performance_record = performance.json()["data"]["records"][0]
    assert performance_record["owned_channel_id"] == channel["id"]
    assert performance_record["platform"] == "xiaohongshu"
    assert performance_record["content_title"] == "高峰期如何减少漏单"
    assert performance_record["metrics"] == {"views": 1200, "likes": 88}

    today = client.get("/api/v1/dashboard/today", headers=headers)
    assert today.status_code == 200
    assert today.json()["data"]["timezone"] == workspace["timezone"]
    assert today.json()["data"]["published_waiting_review_count"] == 0


def test_publish_plan_edit_demotes_approval_and_uses_version_lock(
    client,
    auth_headers,
    workspace,
):
    headers = _headers(auth_headers, workspace)
    channel, project = _ready_project(client, headers)
    plan = client.post(
        "/api/v1/publish-plans",
        headers=headers,
        json={
            "content_project_id": project["id"],
            "owned_channel_id": channel["id"],
            "scheduled_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
            "publish_payload": {"title": "原始标题"},
        },
    ).json()["data"]
    approved = client.post(
        f"/api/v1/publish-plans/{plan['id']}/approve",
        headers=headers,
    ).json()["data"]

    changed = client.patch(
        f"/api/v1/publish-plans/{plan['id']}",
        headers=headers,
        json={
            "version": approved["version"],
            "publish_payload": {"title": "修改后需要重新审核"},
        },
    )
    assert changed.status_code == 200
    assert changed.json()["data"]["status"] == "draft"
    assert changed.json()["data"]["approved_by"] is None

    stale = client.patch(
        f"/api/v1/publish-plans/{plan['id']}",
        headers=headers,
        json={
            "version": approved["version"],
            "publish_payload": {"title": "过期覆盖"},
        },
    )
    assert stale.status_code == 409
