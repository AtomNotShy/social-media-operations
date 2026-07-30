from uuid import UUID

from app.db.models import AnalysisRun, ExternalContent


def _headers(auth_headers, workspace):
    return {**auth_headers, "X-Workspace-Id": workspace["id"]}


def test_pattern_crud_validate_and_retire(client, auth_headers, workspace):
    headers = _headers(auth_headers, workspace)
    created = client.post(
        "/api/v1/patterns",
        headers=headers,
        json={
            "name": "问题—证据—行动",
            "description": "先描述问题，再给证据，最后给行动。",
            "pattern_type": "structure",
        },
    )
    assert created.status_code == 201
    pattern_id = created.json()["data"]["id"]
    assert created.json()["data"]["status"] == "draft"

    updated = client.patch(
        f"/api/v1/patterns/{pattern_id}",
        headers=headers,
        json={"description": "更新后的结构描述"},
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["description"] == "更新后的结构描述"

    validated = client.post(f"/api/v1/patterns/{pattern_id}/validate", headers=headers)
    assert validated.json()["data"]["status"] == "validated"
    cannot_delete = client.delete(f"/api/v1/patterns/{pattern_id}", headers=headers)
    assert cannot_delete.status_code == 409
    retired = client.post(f"/api/v1/patterns/{pattern_id}/retire", headers=headers)
    assert retired.json()["data"]["status"] == "retired"


def test_patterns_can_be_created_from_successful_l2_with_evidence(
    client,
    app,
    auth_headers,
    workspace,
):
    workspace_id = UUID(workspace["id"])
    with app.state.database.session_factory() as db:
        content = ExternalContent(
            workspace_id=workspace_id,
            platform="xiaohongshu",
            external_id="pattern-source",
            canonical_url="https://www.xiaohongshu.com/explore/pattern-source",
            content_type="image_text",
            author_snapshot={},
            media_manifest=[],
        )
        db.add(content)
        db.flush()
        analysis = AnalysisRun(
            workspace_id=workspace_id,
            external_content_id=content.id,
            analysis_level="l2",
            model_provider="fixture",
            model="fixture-l2",
            prompt_version="l1-v1:l2",
            input_hash="pattern-analysis",
            status="succeeded",
            result={
                "reusable_patterns": ["三秒痛点钩子", "错误示范后给解决方案"],
            },
            evidence_refs=[f"content:{content.id}"],
        )
        db.add(analysis)
        db.commit()
        analysis_id = analysis.id

    response = client.post(
        f"/api/v1/patterns/from-analysis/{analysis_id}",
        headers=_headers(auth_headers, workspace),
    )

    assert response.status_code == 201
    patterns = response.json()["data"]
    assert [item["name"] for item in patterns] == [
        "三秒痛点钩子",
        "错误示范后给解决方案",
    ]
    assert patterns[0]["evidence"]["analysis_id"] == str(analysis_id)
