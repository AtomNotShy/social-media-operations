import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import (
    WorkspaceContext,
    get_app_settings,
    get_db,
    get_workspace_context,
    require_editor,
)
from app.core.config import Settings
from app.core.errors import AppError
from app.db.models import Asset, AssetUploadIntent
from app.modules.workflow.schemas import (
    AssetCompleteRequest,
    AssetRead,
    AssetUploadIntentRead,
    AssetUploadIntentRequest,
)
from app.modules.workflow.service import get_project
from app.providers.storage import StorageError, build_object_storage
from app.schemas.common import DataResponse, ResponseMeta

router = APIRouter(prefix="/api/v1/assets", tags=["assets"])

ALLOWED_MIME_PREFIXES = ("image/", "video/", "audio/", "text/")
ALLOWED_EXACT_MIMES = {"application/pdf", "application/json"}


def _require_storage(settings: Settings) -> None:
    if settings.object_storage_provider == "disabled":
        raise AppError(
            409,
            "OBJECT_STORAGE_NOT_CONFIGURED",
            "Object storage is not configured",
            "Configure an approved object-storage provider before uploading assets.",
        )


def _storage_error(error: StorageError) -> AppError:
    statuses = {
        "OBJECT_STORAGE_NOT_CONFIGURED": 409,
        "OBJECT_NOT_UPLOADED": 409,
        "UPLOAD_VERIFICATION_FAILED": 409,
        "INVALID_CHECKSUM": 422,
        "OBJECT_STORAGE_UNAVAILABLE": 503,
    }
    return AppError(
        statuses.get(error.code, 503),
        error.code,
        "Object storage request failed",
        error.message,
    )


@router.post(
    "/upload-intents",
    response_model=DataResponse[AssetUploadIntentRead],
    status_code=status.HTTP_201_CREATED,
)
def create_upload_intent(
    body: AssetUploadIntentRequest,
    request: Request,
    context: WorkspaceContext = Depends(require_editor),
    settings: Settings = Depends(get_app_settings),
    db: Session = Depends(get_db),
) -> DataResponse:
    _require_storage(settings)
    if body.size_bytes > settings.max_asset_size_bytes:
        raise AppError(
            422,
            "VALIDATION_ERROR",
            "Asset is too large",
            f"Assets cannot exceed {settings.max_asset_size_bytes} bytes.",
        )
    if not (
        body.mime_type.startswith(ALLOWED_MIME_PREFIXES) or body.mime_type in ALLOWED_EXACT_MIMES
    ):
        raise AppError(
            422,
            "VALIDATION_ERROR",
            "Unsupported asset type",
            "The requested MIME type is not allowed.",
        )
    if body.source_type == "reference" and not body.rights_note:
        raise AppError(
            422,
            "VALIDATION_ERROR",
            "Rights note required",
            "Reference assets require a rights and source note.",
        )
    if body.content_project_id is not None:
        get_project(
            db,
            workspace_id=context.workspace.id,
            project_id=body.content_project_id,
        )
    intent_id = uuid.uuid4()
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    project_part = str(body.content_project_id) if body.content_project_id else "library"
    storage_key = f"{context.workspace.id}/{project_part}/{intent_id}"
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)
    intent = AssetUploadIntent(
        id=intent_id,
        workspace_id=context.workspace.id,
        content_project_id=body.content_project_id,
        asset_type=body.asset_type,
        storage_key=storage_key,
        mime_type=body.mime_type,
        size_bytes=body.size_bytes,
        checksum=body.checksum.lower(),
        source_type=body.source_type,
        rights_note=body.rights_note,
        token_hash=token_hash,
        expires_at=expires_at,
        created_by=context.membership.user_id,
    )
    db.add(intent)
    storage = build_object_storage(settings)
    try:
        upload = storage.create_upload(
            storage_key=storage_key,
            mime_type=body.mime_type,
            checksum=body.checksum.lower(),
            expires_in_seconds=900,
        )
    except StorageError as exc:
        raise _storage_error(exc) from exc
    db.commit()
    return DataResponse(
        data=AssetUploadIntentRead(
            intent_id=intent.id,
            upload_url=upload.url,
            upload_token=raw_token,
            storage_key=storage_key,
            expires_at=expires_at,
            required_headers=upload.required_headers,
        ),
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.post(
    "/complete",
    response_model=DataResponse[AssetRead],
    status_code=status.HTTP_201_CREATED,
)
def complete_upload(
    body: AssetCompleteRequest,
    request: Request,
    context: WorkspaceContext = Depends(require_editor),
    settings: Settings = Depends(get_app_settings),
    db: Session = Depends(get_db),
) -> DataResponse:
    _require_storage(settings)
    intent = db.scalar(
        select(AssetUploadIntent).where(
            AssetUploadIntent.workspace_id == context.workspace.id,
            AssetUploadIntent.id == body.intent_id,
        )
    )
    if intent is None:
        raise AppError(404, "NOT_FOUND", "Upload intent not found", "Intent not found.")
    supplied_hash = hashlib.sha256(body.upload_token.encode()).hexdigest()
    if not secrets.compare_digest(supplied_hash, intent.token_hash):
        raise AppError(
            403,
            "FORBIDDEN",
            "Invalid upload token",
            "The upload completion token is invalid.",
        )
    existing = db.scalar(select(Asset).where(Asset.storage_key == intent.storage_key))
    if existing is not None:
        return DataResponse(
            data=AssetRead.model_validate(existing),
            meta=ResponseMeta(request_id=request.state.request_id),
        )
    expires_at = (
        intent.expires_at
        if intent.expires_at.tzinfo is not None
        else intent.expires_at.replace(tzinfo=timezone.utc)
    )
    if expires_at < datetime.now(timezone.utc):
        raise AppError(
            409,
            "UPLOAD_INTENT_EXPIRED",
            "Upload intent expired",
            "Create a new upload intent and upload the asset again.",
        )
    if intent.status != "pending":
        raise AppError(
            409,
            "VERSION_CONFLICT",
            "Upload intent is not pending",
            "This upload intent cannot be completed.",
        )
    storage = build_object_storage(settings)
    try:
        storage.verify_upload(
            storage_key=intent.storage_key,
            expected_size_bytes=intent.size_bytes,
            expected_mime_type=intent.mime_type,
            expected_checksum=intent.checksum,
        )
    except StorageError as exc:
        raise _storage_error(exc) from exc
    asset = Asset(
        workspace_id=context.workspace.id,
        content_project_id=intent.content_project_id,
        asset_type=intent.asset_type,
        storage_key=intent.storage_key,
        mime_type=intent.mime_type,
        size_bytes=intent.size_bytes,
        checksum=intent.checksum,
        source_type=intent.source_type,
        rights_note=intent.rights_note,
        created_by=intent.created_by,
    )
    db.add(asset)
    intent.status = "completed"
    db.commit()
    return DataResponse(
        data=AssetRead.model_validate(asset),
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.get("", response_model=DataResponse[list[AssetRead]])
def list_assets(
    request: Request,
    content_project_id: uuid.UUID | None = None,
    context: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db),
) -> DataResponse:
    query = select(Asset).where(
        Asset.workspace_id == context.workspace.id,
        Asset.deleted_at.is_(None),
    )
    if content_project_id is not None:
        query = query.where(Asset.content_project_id == content_project_id)
    assets = db.scalars(query.order_by(Asset.created_at.desc())).all()
    return DataResponse(
        data=[AssetRead.model_validate(item) for item in assets],
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.get("/{asset_id}", response_model=DataResponse[AssetRead])
def get_asset(
    asset_id: uuid.UUID,
    request: Request,
    context: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db),
) -> DataResponse:
    asset = db.scalar(
        select(Asset).where(
            Asset.workspace_id == context.workspace.id,
            Asset.id == asset_id,
            Asset.deleted_at.is_(None),
        )
    )
    if asset is None:
        raise AppError(404, "NOT_FOUND", "Asset not found", "Asset not found.")
    return DataResponse(
        data=AssetRead.model_validate(asset),
        meta=ResponseMeta(request_id=request.state.request_id),
    )


@router.delete("/{asset_id}", response_model=DataResponse[AssetRead])
def delete_asset(
    asset_id: uuid.UUID,
    request: Request,
    context: WorkspaceContext = Depends(require_editor),
    db: Session = Depends(get_db),
) -> DataResponse:
    asset = db.scalar(
        select(Asset).where(
            Asset.workspace_id == context.workspace.id,
            Asset.id == asset_id,
            Asset.deleted_at.is_(None),
        )
    )
    if asset is None:
        raise AppError(404, "NOT_FOUND", "Asset not found", "Asset not found.")
    asset.deleted_at = datetime.now(timezone.utc)
    db.commit()
    return DataResponse(
        data=AssetRead.model_validate(asset),
        meta=ResponseMeta(request_id=request.state.request_id),
    )
