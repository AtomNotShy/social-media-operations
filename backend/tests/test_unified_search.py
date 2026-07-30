from uuid import UUID

from app.db.models import ExternalContent, ReusablePattern, WorkspaceInspiration


def _headers(auth_headers, workspace):
    return {**auth_headers, "X-Workspace-Id": workspace["id"]}


def test_unified_search_returns_explainable_workspace_scoped_results(
    client,
    app,
    auth_headers,
    workspace,
):
    other = client.post(
        "/api/v1/workspaces",
        headers=auth_headers,
        json={"name": "Other workspace", "timezone": "UTC"},
    ).json()["data"]
    with app.state.database.session_factory() as db:
        content = ExternalContent(
            workspace_id=UUID(workspace["id"]),
            platform="xiaohongshu",
            external_id="searchable-content",
            canonical_url="https://www.xiaohongshu.com/explore/searchable-content",
            content_type="image_text",
            title="餐饮门店增长方法",
            body_text="用复购和套餐设计改善经营。",
            author_snapshot={},
            media_manifest=[],
        )
        db.add(content)
        db.flush()
        db.add_all(
            [
                WorkspaceInspiration(
                    workspace_id=UUID(workspace["id"]),
                    external_content_id=content.id,
                    source="test",
                ),
                ReusablePattern(
                    workspace_id=UUID(workspace["id"]),
                    name="餐饮开场钩子",
                    description="适合门店经营内容。",
                    pattern_type="hook",
                ),
                ReusablePattern(
                    workspace_id=UUID(other["id"]),
                    name="餐饮秘密资料",
                    description="不应跨工作区出现。",
                    pattern_type="hook",
                ),
            ]
        )
        db.commit()

    response = client.get(
        "/api/v1/search",
        params={"q": "餐饮"},
        headers=_headers(auth_headers, workspace),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert {item["entity_type"] for item in data} == {"inspiration", "pattern"}
    assert all(item["matched_fields"] for item in data)
    assert all(item["source_ref"].startswith("/api/v1/") for item in data)
    assert all("秘密" not in item["title"] for item in data)


def test_unified_search_can_filter_entity_type(client, app, auth_headers, workspace):
    with app.state.database.session_factory() as db:
        db.add(
            ReusablePattern(
                workspace_id=UUID(workspace["id"]),
                name="Only pattern result",
                description="Filter fixture",
                pattern_type="hook",
            )
        )
        db.commit()

    response = client.get(
        "/api/v1/search",
        params=[("q", "pattern"), ("type", "pattern")],
        headers=_headers(auth_headers, workspace),
    )

    assert response.status_code == 200
    assert [item["entity_type"] for item in response.json()["data"]] == ["pattern"]
