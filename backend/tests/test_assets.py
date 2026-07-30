def _headers(auth_headers, workspace):
    return {**auth_headers, "X-Workspace-Id": workspace["id"]}


def _intent_body():
    return {
        "asset_type": "image",
        "mime_type": "image/png",
        "size_bytes": 1024,
        "checksum": "a" * 64,
        "source_type": "uploaded",
    }


def test_asset_upload_rejects_unconfigured_storage(client, auth_headers, workspace):
    response = client.post(
        "/api/v1/assets/upload-intents",
        headers=_headers(auth_headers, workspace),
        json=_intent_body(),
    )

    assert response.status_code == 409
    assert response.json()["code"] == "OBJECT_STORAGE_NOT_CONFIGURED"


def test_fixture_upload_intent_token_completion_and_soft_delete(
    client,
    app,
    auth_headers,
    workspace,
):
    app.state.settings.object_storage_provider = "fixture"
    headers = _headers(auth_headers, workspace)
    intent_response = client.post(
        "/api/v1/assets/upload-intents",
        headers=headers,
        json=_intent_body(),
    )
    assert intent_response.status_code == 201
    intent = intent_response.json()["data"]
    assert intent["upload_url"].startswith("https://storage.example.invalid/")
    assert intent["required_headers"]["X-Content-SHA256"] == "a" * 64

    denied = client.post(
        "/api/v1/assets/complete",
        headers=headers,
        json={"intent_id": intent["intent_id"], "upload_token": "x" * 32},
    )
    assert denied.status_code == 403

    completed = client.post(
        "/api/v1/assets/complete",
        headers=headers,
        json={
            "intent_id": intent["intent_id"],
            "upload_token": intent["upload_token"],
        },
    )
    assert completed.status_code == 201
    asset = completed.json()["data"]
    assert asset["checksum"] == "a" * 64

    repeated = client.post(
        "/api/v1/assets/complete",
        headers=headers,
        json={
            "intent_id": intent["intent_id"],
            "upload_token": intent["upload_token"],
        },
    )
    assert repeated.status_code == 201
    assert repeated.json()["data"]["id"] == asset["id"]

    deleted = client.delete(f"/api/v1/assets/{asset['id']}", headers=headers)
    assert deleted.status_code == 200
    listing = client.get("/api/v1/assets", headers=headers)
    assert listing.json()["data"] == []


def test_reference_asset_requires_rights_note(client, app, auth_headers, workspace):
    app.state.settings.object_storage_provider = "fixture"
    body = _intent_body()
    body["source_type"] = "reference"

    response = client.post(
        "/api/v1/assets/upload-intents",
        headers=_headers(auth_headers, workspace),
        json=body,
    )

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"
