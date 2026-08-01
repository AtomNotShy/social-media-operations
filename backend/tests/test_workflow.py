from uuid import UUID

from app.db.models import ExternalContent, WorkspaceInspiration


def _headers(auth_headers, workspace):
    return {**auth_headers, "X-Workspace-Id": workspace["id"]}


def _create_channel(client, headers):
    response = client.post(
        "/api/v1/owned-channels",
        headers=headers,
        json={
            "platform": "xiaohongshu",
            "display_name": "自有餐饮账号",
            "positioning": "帮助独立餐厅提升运营效率",
            "audience": {"primary": "餐厅老板"},
            "content_pillars": ["高峰运营", "成本控制"],
            "tone_rules": ["具体", "诚实"],
            "prohibited_topics": ["无证据收益承诺"],
        },
    )
    assert response.status_code == 201
    return response.json()["data"]


def test_owned_channel_positioning_and_soft_disable(client, auth_headers, workspace):
    headers = _headers(auth_headers, workspace)
    channel = _create_channel(client, headers)

    updated = client.put(
        f"/api/v1/owned-channels/{channel['id']}/positioning",
        headers=headers,
        json={
            "positioning": "更新后的定位",
            "audience": {"primary": "快餐店老板"},
            "content_pillars": ["排班"],
            "tone_rules": ["直接"],
            "prohibited_topics": [],
        },
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["positioning"] == "更新后的定位"

    disabled = client.delete(
        f"/api/v1/owned-channels/{channel['id']}",
        headers=headers,
    )
    assert disabled.status_code == 200
    assert disabled.json()["data"]["active"] is False
    assert disabled.json()["data"]["publishing_mode"] == "disabled"


def test_topic_optimistic_lock_and_inspiration_evidence(
    client,
    app,
    auth_headers,
    workspace,
):
    headers = _headers(auth_headers, workspace)
    channel = _create_channel(client, headers)
    with app.state.database.session_factory() as db:
        content = ExternalContent(
            workspace_id=UUID(workspace["id"]),
            platform="xiaohongshu",
            external_id="topic-source",
            canonical_url="https://www.xiaohongshu.com/explore/topic-source",
            content_type="image_text",
            title="如何减少高峰期漏单",
            author_snapshot={},
            media_manifest=[],
        )
        db.add(content)
        db.flush()
        inspiration = WorkspaceInspiration(
            workspace_id=UUID(workspace["id"]),
            external_content_id=content.id,
            source="test",
        )
        db.add(inspiration)
        db.commit()
        inspiration_id = inspiration.id

    created = client.post(
        f"/api/v1/topics/from-inspiration/{inspiration_id}",
        headers=headers,
        json={"owned_channel_id": channel["id"]},
    )
    assert created.status_code == 201
    topic = created.json()["data"]
    assert topic["title"] == "如何减少高峰期漏单"
    assert topic["evidence_refs"][0] == f"inspiration:{inspiration_id}"
    inspiration_response = client.get(
        f"/api/v1/inspirations/{inspiration_id}", headers=headers
    )
    assert inspiration_response.json()["data"]["status"] == "candidate"

    updated = client.patch(
        f"/api/v1/topics/{topic['id']}",
        headers=headers,
        json={"version": 1, "angle": "从出单流程切入"},
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["version"] == 2
    stale = client.patch(
        f"/api/v1/topics/{topic['id']}",
        headers=headers,
        json={"version": 1, "angle": "覆盖别人修改"},
    )
    assert stale.status_code == 409
    assert stale.json()["code"] == "VERSION_CONFLICT"


def test_project_state_machine_and_append_only_scripts(
    client,
    auth_headers,
    workspace,
):
    headers = _headers(auth_headers, workspace)
    channel = _create_channel(client, headers)
    topic = client.post(
        "/api/v1/topics",
        headers=headers,
        json={
            "owned_channel_id": channel["id"],
            "title": "高峰期漏单解决方案",
            "status": "selected",
        },
    ).json()["data"]
    project = client.post(
        "/api/v1/content-projects",
        headers=headers,
        json={
            "topic_id": topic["id"],
            "owned_channel_id": channel["id"],
            "title": "高峰期漏单短视频",
        },
    ).json()["data"]
    assert project["status"] == "idea"
    assert project["version"] == 1

    invalid = client.post(
        f"/api/v1/content-projects/{project['id']}/transition",
        headers=headers,
        json={"from": "idea", "to": "producing", "version": 1},
    )
    assert invalid.status_code == 409
    assert invalid.json()["code"] == "INVALID_STATE_TRANSITION"

    first_script = client.post(
        f"/api/v1/content-projects/{project['id']}/scripts",
        headers=headers,
        json={
            "project_version": 1,
            "body": "开头：你是否在高峰期漏过单？",
            "change_note": "首稿",
        },
    )
    assert first_script.status_code == 201
    assert first_script.json()["data"]["version_no"] == 1
    after_first = client.get(
        f"/api/v1/content-projects/{project['id']}",
        headers=headers,
    ).json()["data"]
    assert after_first["status"] == "scripting"
    assert after_first["version"] == 2

    stale_script = client.post(
        f"/api/v1/content-projects/{project['id']}/scripts",
        headers=headers,
        json={"project_version": 1, "body": "过期编辑"},
    )
    assert stale_script.status_code == 409

    duplicated = client.post(
        f"/api/v1/content-projects/{project['id']}/scripts/1/duplicate",
        headers=headers,
        json={"project_version": 2, "change_note": "用于新分支"},
    )
    assert duplicated.status_code == 201
    assert duplicated.json()["data"]["version_no"] == 2
    scripts = client.get(
        f"/api/v1/content-projects/{project['id']}/scripts",
        headers=headers,
    ).json()["data"]
    assert [item["version_no"] for item in scripts] == [2, 1]

    transitioned = client.post(
        f"/api/v1/content-projects/{project['id']}/transition",
        headers=headers,
        json={"from": "scripting", "to": "producing", "version": 3},
    )
    assert transitioned.status_code == 200
    assert transitioned.json()["data"]["status"] == "producing"
    assert transitioned.json()["data"]["version"] == 4
