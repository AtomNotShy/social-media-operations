from dataclasses import dataclass
from typing import Any

from app.providers.social.tikhub.bilibili import BilibiliAdapter
from app.providers.social.tikhub.douyin import DouyinAppV3Adapter
from app.providers.social.tikhub.twitter import TwitterAdapter
from app.providers.social.tikhub.xiaohongshu import XiaohongshuAppV2Adapter


@dataclass(frozen=True, slots=True)
class TikHubPlatformBinding:
    platform: str
    series: str
    profile_endpoint: str
    contents_endpoint: str
    detail_endpoint: str
    comments_endpoint: str
    adapter: Any

    def profile_params(self, external_id: str) -> dict[str, Any]:
        if self.platform == "x":
            return _x_user_params(external_id)
        return {
            "xiaohongshu": {"user_id": external_id},
            "douyin": {"sec_user_id": external_id},
            "bilibili": {"user_id": external_id},
        }[self.platform]

    def contents_params(
        self,
        external_id: str,
        cursor: str | None,
        limit: int,
    ) -> dict[str, Any]:
        if self.platform == "x":
            params = _x_user_params(external_id)
            if cursor:
                params["cursor"] = cursor
            return params
        if self.platform == "xiaohongshu":
            return {"user_id": external_id, "cursor": cursor}
        if self.platform == "douyin":
            return {
                "sec_user_id": external_id,
                "max_cursor": int(cursor or 0),
                "count": min(limit, 20),
                "sort_type": 0,
            }
        return {
            "user_id": external_id,
            "post_filter": "archive",
            "page": int(cursor or 1),
            "ps": min(limit, 20),
        }

    def detail_params(self, external_id: str | None, canonical_url: str) -> dict[str, Any]:
        if self.platform == "x":
            return {"tweet_id": external_id} if external_id else {"url": canonical_url}
        if self.platform == "xiaohongshu":
            return {"note_id": external_id} if external_id else {"share_text": canonical_url}
        if self.platform == "douyin":
            return {"aweme_id": external_id}
        return {"url": canonical_url}

    def comment_params(
        self,
        external_id: str,
        cursor: str | None,
        limit: int,
        sort_strategy: str,
    ) -> dict[str, Any]:
        if self.platform == "x":
            return {"tweet_id": external_id, "cursor": cursor}
        if self.platform == "xiaohongshu":
            return {
                "note_id": external_id,
                "cursor": cursor,
                "index": 0,
                "pageArea": "UNFOLDED",
                "sort_strategy": sort_strategy,
            }
        if self.platform == "douyin":
            return {
                "aweme_id": external_id,
                "cursor": int(cursor or 0),
                "count": min(limit, 20),
            }
        key = "bv_id" if external_id.upper().startswith("BV") else "av_id"
        return {
            key: external_id,
            "mode": 3,
            "next_offset": cursor,
        }


def _x_user_params(external_id: str) -> dict[str, Any]:
    if external_id.isdigit():
        return {"rest_id": int(external_id)}
    return {"screen_name": external_id}


PLATFORM_BINDINGS = {
    "x": TikHubPlatformBinding(
        platform="x",
        series="web",
        profile_endpoint="x.profile",
        contents_endpoint="x.profile_contents",
        detail_endpoint="x.content_detail",
        comments_endpoint="x.comments",
        adapter=TwitterAdapter(),
    ),
    "xiaohongshu": TikHubPlatformBinding(
        platform="xiaohongshu",
        series="app_v2",
        profile_endpoint="xhs.profile",
        contents_endpoint="xhs.profile_contents",
        detail_endpoint="xhs.content_image_detail",
        comments_endpoint="xhs.comments",
        adapter=XiaohongshuAppV2Adapter(),
    ),
    "douyin": TikHubPlatformBinding(
        platform="douyin",
        series="app_v3",
        profile_endpoint="douyin.profile",
        contents_endpoint="douyin.profile_contents",
        detail_endpoint="douyin.content_detail",
        comments_endpoint="douyin.comments",
        adapter=DouyinAppV3Adapter(),
    ),
    "bilibili": TikHubPlatformBinding(
        platform="bilibili",
        series="app_web",
        profile_endpoint="bilibili.profile",
        contents_endpoint="bilibili.profile_contents",
        detail_endpoint="bilibili.content_detail",
        comments_endpoint="bilibili.comments",
        adapter=BilibiliAdapter(),
    ),
}


def get_platform_binding(platform: str) -> TikHubPlatformBinding:
    try:
        return PLATFORM_BINDINGS[platform]
    except KeyError as exc:
        raise ValueError(f"TikHub platform is not implemented: {platform}") from exc
