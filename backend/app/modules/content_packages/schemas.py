from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

CONTENT_PACKAGE_SCHEMA_VERSION = 1
# DeepSeek-family models count reasoning tokens toward max_tokens; a content
# package (scene splits + titles + cover + caption + assets) needs far more
# output budget than a spoken script.
CONTENT_PACKAGE_MIN_MAX_TOKENS = 16000

SceneLayout = Literal["avatar_full", "avatar_corner", "broll", "comparison", "cta"]
ContentPackageStatus = Literal["draft", "frozen"]


class ContentPackageGenerateRequest(BaseModel):
    project_version: int = Field(ge=1)
    script_version_id: UUID
    target_platform: str = Field(min_length=1, max_length=32)
    force: bool = False


class ContentPackageNarration(BaseModel):
    full_text: str = Field(min_length=1, max_length=100000)
    spoken_length_chars: int = Field(ge=1)
    estimated_duration_seconds: int = Field(ge=1)


class ContentPackageScene(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    layout: SceneLayout
    narration_chunk: str = Field(min_length=1, max_length=20000)
    visual_hint: str = Field(min_length=1, max_length=2000)
    on_screen_text: str | None = Field(default=None, max_length=500)
    subtitle: str = Field(min_length=1, max_length=2000)
    estimated_seconds: int = Field(ge=1)
    cta: str | None = Field(default=None, max_length=500)
    asset_queries: list[str] = Field(default_factory=list, max_length=50)
    evidence_refs: list[str] = Field(default_factory=list, max_length=100)


class ContentPackageTitleCandidate(BaseModel):
    text: str = Field(min_length=1, max_length=200)
    length_chars: int = Field(ge=1)
    has_emoji: bool = False


class ContentPackageCover(BaseModel):
    headline: str = Field(min_length=1, max_length=200)
    subheadline: str | None = Field(default=None, max_length=200)
    visual_hint: str | None = Field(default=None, max_length=1000)


class ContentPackageAssetRequirement(BaseModel):
    kind: str = Field(min_length=1, max_length=32)
    query: str = Field(min_length=1, max_length=500)
    source_hint: str | None = Field(default=None, max_length=255)
    rights_note: str | None = Field(default=None, max_length=2000)


class ContentPackageAudio(BaseModel):
    voice_hint: str = Field(min_length=1, max_length=500)
    music_mood: str | None = Field(default=None, max_length=500)
    music_ducking: str | None = Field(default=None, max_length=100)


class GeneratedContentPackageResult(BaseModel):
    """The AI-produced contract consumed by editors and render adapters."""

    schema_version: int = CONTENT_PACKAGE_SCHEMA_VERSION
    target_platform: str = Field(min_length=1, max_length=32)
    content_type: str = Field(min_length=1, max_length=32)
    target_duration_seconds: int = Field(ge=1)
    narration: ContentPackageNarration
    scenes: list[ContentPackageScene] = Field(min_length=1, max_length=100)
    title_candidates: list[ContentPackageTitleCandidate] = Field(
        min_length=1, max_length=5
    )
    cover: ContentPackageCover
    hashtags: list[str] = Field(max_length=20)
    publish_caption: str = Field(min_length=1, max_length=2000)
    assets_required: list[ContentPackageAssetRequirement] = Field(
        default_factory=list, max_length=50
    )
    audio: ContentPackageAudio
    publish_timing_hint: str | None = Field(default=None, max_length=500)
    evidence_refs: list[str] = Field(min_length=1, max_length=100)

    @field_validator("scenes")
    @classmethod
    def _scene_ids_unique(
        cls, scenes: list[ContentPackageScene]
    ) -> list[ContentPackageScene]:
        ids = [scene.id for scene in scenes]
        if len(ids) != len(set(ids)):
            raise ValueError("scene ids must be unique")
        return scenes


class ContentPackageEdit(BaseModel):
    """Partial manual edits; the edited copy gets a new version number."""

    target_duration_seconds: int | None = Field(default=None, ge=1)
    scenes: list[ContentPackageScene] | None = Field(default=None, min_length=1)
    title_candidates: list[ContentPackageTitleCandidate] | None = Field(
        default=None, min_length=1, max_length=5
    )
    cover: ContentPackageCover | None = None
    hashtags: list[str] | None = Field(default=None, max_length=20)
    publish_caption: str | None = Field(default=None, min_length=1, max_length=2000)
    assets_required: list[ContentPackageAssetRequirement] | None = Field(
        default=None, max_length=50
    )
    audio: ContentPackageAudio | None = None
    publish_timing_hint: str | None = Field(default=None, max_length=500)


class ContentPackageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    content_project_id: UUID
    script_version_id: UUID | None
    generation_run_id: UUID | None
    schema_version: int
    target_platform: str
    status: str
    version: int
    package: dict
    evidence_refs: list
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime
