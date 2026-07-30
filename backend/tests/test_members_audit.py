from sqlalchemy import select

from app.db.models import User


def _headers(auth_headers, workspace):
    return {**auth_headers, "X-Workspace-Id": workspace["id"]}


def test_only_owner_manages_members_and_last_owner_is_protected(
    client,
    app,
    auth_headers,
    workspace,
):
    owner_headers = _headers(auth_headers, workspace)
    editor_auth = {"Authorization": "Bearer dev:team-editor"}
    assert client.get("/api/v1/me", headers=editor_auth).status_code == 200
    with app.state.database.session_factory() as db:
        editor = db.scalar(select(User).where(User.external_subject == "team-editor"))
        editor_id = editor.id
        owner = db.scalar(select(User).where(User.external_subject == "test-owner"))
        owner_id = owner.id

    added = client.post(
        f"/api/v1/workspaces/{workspace['id']}/members",
        headers=owner_headers,
        json={"user_id": str(editor_id), "role": "editor"},
    )
    assert added.status_code == 201
    assert added.json()["data"]["role"] == "editor"

    editor_headers = {**editor_auth, "X-Workspace-Id": workspace["id"]}
    forbidden = client.get(
        f"/api/v1/workspaces/{workspace['id']}/members",
        headers=editor_headers,
    )
    assert forbidden.status_code == 403

    last_owner = client.patch(
        f"/api/v1/workspaces/{workspace['id']}/members/{owner_id}",
        headers=owner_headers,
        json={"role": "viewer"},
    )
    assert last_owner.status_code == 409
    assert last_owner.json()["code"] == "LAST_OWNER_REQUIRED"

    promoted = client.patch(
        f"/api/v1/workspaces/{workspace['id']}/members/{editor_id}",
        headers=owner_headers,
        json={"role": "owner"},
    )
    assert promoted.status_code == 200
    demoted = client.patch(
        f"/api/v1/workspaces/{workspace['id']}/members/{owner_id}",
        headers=owner_headers,
        json={"role": "viewer"},
    )
    assert demoted.status_code == 200


def test_authenticated_mutations_are_audited_without_request_body(
    client,
    auth_headers,
    workspace,
):
    headers = _headers(auth_headers, workspace)
    created = client.post(
        "/api/v1/owned-channels",
        headers=headers,
        json={
            "platform": "xiaohongshu",
            "display_name": "审计账号",
            "positioning": "This body must not be copied into audit metadata.",
        },
    )
    assert created.status_code == 201

    events = client.get("/api/v1/audit-events", headers=headers)
    assert events.status_code == 200
    matching = [item for item in events.json()["data"] if item["path"] == "/api/v1/owned-channels"]
    assert len(matching) == 1
    assert matching[0]["action"] == "POST"
    assert matching[0]["response_status"] == 201
    assert matching[0]["metadata_json"] == {}
