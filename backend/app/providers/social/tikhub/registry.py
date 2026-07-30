from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class TikHubEndpoint:
    key: str
    platform: str
    path: str
    version: str
    estimated_cost_usd: Decimal
    freshness_seconds: int
    timeout_seconds: float = 45.0
    max_attempts: int = 3


ENDPOINTS: dict[str, TikHubEndpoint] = {
    "xhs.profile": TikHubEndpoint(
        key="xhs.profile",
        platform="xiaohongshu",
        path="/api/v1/xiaohongshu/app_v2/get_user_info",
        version="app_v2",
        estimated_cost_usd=Decimal("0.001"),
        freshness_seconds=24 * 60 * 60,
    ),
    "xhs.profile_contents": TikHubEndpoint(
        key="xhs.profile_contents",
        platform="xiaohongshu",
        path="/api/v1/xiaohongshu/app_v2/get_user_posted_notes",
        version="app_v2",
        estimated_cost_usd=Decimal("0.001"),
        freshness_seconds=3 * 60 * 60,
    ),
    "xhs.content_image_detail": TikHubEndpoint(
        key="xhs.content_image_detail",
        platform="xiaohongshu",
        path="/api/v1/xiaohongshu/app_v2/get_image_note_detail",
        version="app_v2",
        estimated_cost_usd=Decimal("0.001"),
        freshness_seconds=24 * 60 * 60,
    ),
    "xhs.content_video_detail": TikHubEndpoint(
        key="xhs.content_video_detail",
        platform="xiaohongshu",
        path="/api/v1/xiaohongshu/app_v2/get_video_note_detail",
        version="app_v2",
        estimated_cost_usd=Decimal("0.001"),
        freshness_seconds=24 * 60 * 60,
    ),
    "xhs.comments": TikHubEndpoint(
        key="xhs.comments",
        platform="xiaohongshu",
        path="/api/v1/xiaohongshu/app_v2/get_note_comments",
        version="app_v2",
        estimated_cost_usd=Decimal("0.001"),
        freshness_seconds=24 * 60 * 60,
    ),
    "xhs.search_notes": TikHubEndpoint(
        key="xhs.search_notes",
        platform="xiaohongshu",
        path="/api/v1/xiaohongshu/app_v2/search_notes",
        version="app_v2",
        estimated_cost_usd=Decimal("0.001"),
        freshness_seconds=60 * 60,
    ),
    "douyin.profile": TikHubEndpoint(
        key="douyin.profile",
        platform="douyin",
        path="/api/v1/douyin/app/v3/handler_user_profile",
        version="app_v3",
        estimated_cost_usd=Decimal("0.001"),
        freshness_seconds=24 * 60 * 60,
    ),
    "douyin.profile_contents": TikHubEndpoint(
        key="douyin.profile_contents",
        platform="douyin",
        path="/api/v1/douyin/app/v3/fetch_user_post_videos",
        version="app_v3",
        estimated_cost_usd=Decimal("0.001"),
        freshness_seconds=3 * 60 * 60,
    ),
    "douyin.content_detail": TikHubEndpoint(
        key="douyin.content_detail",
        platform="douyin",
        path="/api/v1/douyin/app/v3/fetch_one_video_v3",
        version="app_v3",
        estimated_cost_usd=Decimal("0.001"),
        freshness_seconds=24 * 60 * 60,
    ),
    "douyin.comments": TikHubEndpoint(
        key="douyin.comments",
        platform="douyin",
        path="/api/v1/douyin/app/v3/fetch_video_comments",
        version="app_v3",
        estimated_cost_usd=Decimal("0.001"),
        freshness_seconds=24 * 60 * 60,
    ),
    "bilibili.profile": TikHubEndpoint(
        key="bilibili.profile",
        platform="bilibili",
        path="/api/v1/bilibili/app/fetch_user_info",
        version="app",
        estimated_cost_usd=Decimal("0.001"),
        freshness_seconds=24 * 60 * 60,
    ),
    "bilibili.profile_contents": TikHubEndpoint(
        key="bilibili.profile_contents",
        platform="bilibili",
        path="/api/v1/bilibili/app/fetch_user_videos",
        version="app",
        estimated_cost_usd=Decimal("0.001"),
        freshness_seconds=3 * 60 * 60,
    ),
    "bilibili.content_detail": TikHubEndpoint(
        key="bilibili.content_detail",
        platform="bilibili",
        path="/api/v1/bilibili/web/fetch_one_video_v3",
        version="web_v3",
        estimated_cost_usd=Decimal("0.001"),
        freshness_seconds=24 * 60 * 60,
    ),
    "bilibili.comments": TikHubEndpoint(
        key="bilibili.comments",
        platform="bilibili",
        path="/api/v1/bilibili/app/fetch_video_comments",
        version="app",
        estimated_cost_usd=Decimal("0.001"),
        freshness_seconds=24 * 60 * 60,
    ),
}


def get_endpoint(key: str) -> TikHubEndpoint:
    try:
        return ENDPOINTS[key]
    except KeyError as exc:
        raise ValueError(f"Unknown TikHub endpoint key: {key}") from exc
