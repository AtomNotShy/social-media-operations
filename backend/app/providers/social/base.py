from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class ExternalReference:
    platform: str
    external_id: str
    canonical_url: str
    reference_type: str


@dataclass(frozen=True, slots=True)
class ContentMetrics:
    views: int | None = None
    likes: int | None = None
    comments: int | None = None
    favorites: int | None = None
    shares: int | None = None
    downloads: int | None = None


@dataclass(frozen=True, slots=True)
class NormalizedProfile:
    platform: str
    external_id: str
    display_name: str
    handle: str | None
    bio: str | None
    avatar_url: str | None
    followers: int | None
    following: int | None
    total_likes: int | None
    content_count: int | None
    extra_metrics: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class NormalizedContent:
    platform: str
    external_id: str
    canonical_url: str
    content_type: str
    title: str | None
    body_text: str | None
    published_at: datetime | None
    duration_ms: int | None
    author: dict[str, Any]
    metrics: ContentMetrics
    media: list[dict[str, Any]] = field(default_factory=list)
    provider_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class NormalizedComment:
    external_id: str
    parent_external_id: str | None
    author: dict[str, Any]
    body_text: str
    like_count: int | None
    published_at: datetime | None


@dataclass(frozen=True, slots=True)
class CommentPage:
    items: list[NormalizedComment]
    cursor: str | None
    index: int
    page_area: str
    has_more: bool


@dataclass(frozen=True, slots=True)
class SearchPage:
    items: list[NormalizedContent]
    search_id: str | None
    search_session_id: str | None
    has_more: bool


@dataclass(frozen=True, slots=True)
class ProviderResult:
    data: Any
    endpoint_key: str
    provider_request_id: str | None
    raw_response: dict[str, Any]


@dataclass(frozen=True, slots=True)
class ProviderPage:
    items: list[Any]
    next_cursor: str | None
    endpoint_key: str
    provider_request_id: str | None
    raw_response: dict[str, Any]


class SocialDataProvider(Protocol):
    async def resolve_url(self, url: str) -> ExternalReference: ...

    async def fetch_profile(self, ref: ExternalReference) -> ProviderResult: ...

    async def fetch_profile_contents(
        self, ref: ExternalReference, cursor: str | None, limit: int
    ) -> ProviderPage: ...

    async def fetch_content(self, ref: ExternalReference) -> ProviderResult: ...

    async def fetch_metrics(self, ref: ExternalReference) -> ProviderResult: ...

    async def fetch_comments(
        self, ref: ExternalReference, cursor: str | None, limit: int
    ) -> ProviderPage: ...

    async def search(
        self, platform: str, query: str, cursor: str | None, limit: int
    ) -> ProviderPage: ...

    async def fetch_trending(self, platform: str) -> ProviderResult: ...
