import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.models import ContentPackage
from app.modules.content_packages.schemas import (
    ContentPackageEdit,
    ContentPackageRead,
    GeneratedContentPackageResult,
)


def content_package_read(package: ContentPackage) -> ContentPackageRead:
    return ContentPackageRead.model_validate(package)


def get_content_package(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    package_id: uuid.UUID,
) -> ContentPackage:
    package = db.scalar(
        select(ContentPackage).where(
            ContentPackage.workspace_id == workspace_id,
            ContentPackage.id == package_id,
        )
    )
    if package is None:
        raise AppError(
            404,
            "NOT_FOUND",
            "Content package not found",
            "Content package not found.",
        )
    return package


def list_content_packages(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    project_id: uuid.UUID | None = None,
    target_platform: str | None = None,
) -> list[ContentPackage]:
    query = select(ContentPackage).where(
        ContentPackage.workspace_id == workspace_id
    )
    if project_id is not None:
        query = query.where(ContentPackage.content_project_id == project_id)
    if target_platform is not None:
        query = query.where(ContentPackage.target_platform == target_platform)
    return list(db.scalars(query.order_by(ContentPackage.created_at.desc())).all())


def edit_content_package(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    package_id: uuid.UUID,
    body: ContentPackageEdit,
    edited_by: uuid.UUID,
) -> ContentPackage:
    """Create a new edited version; existing rows (including frozen) are kept."""
    current = get_content_package(db, workspace_id=workspace_id, package_id=package_id)
    package_payload = dict(current.package)
    edits = body.model_dump(exclude_unset=True)
    for key, value in edits.items():
        if value is not None:
            package_payload[key] = value
    # Re-validate the merged package so manual edits cannot break the contract.
    GeneratedContentPackageResult.model_validate(package_payload)
    next_version = (
        db.scalar(
            select(ContentPackage.version)
            .where(
                ContentPackage.workspace_id == workspace_id,
                ContentPackage.content_project_id == current.content_project_id,
                ContentPackage.target_platform == current.target_platform,
            )
            .order_by(ContentPackage.version.desc())
            .limit(1)
        )
        or 0
    ) + 1
    edited = ContentPackage(
        workspace_id=workspace_id,
        content_project_id=current.content_project_id,
        script_version_id=current.script_version_id,
        generation_run_id=current.generation_run_id,
        schema_version=current.schema_version,
        target_platform=current.target_platform,
        status="draft",
        version=next_version,
        package=package_payload,
        evidence_refs=package_payload.get("evidence_refs") or current.evidence_refs,
        created_by=edited_by,
    )
    db.add(edited)
    db.flush()
    return edited


def freeze_content_package(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    package_id: uuid.UUID,
) -> ContentPackage:
    package = get_content_package(db, workspace_id=workspace_id, package_id=package_id)
    package.status = "frozen"
    db.flush()
    return package
