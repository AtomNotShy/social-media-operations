from typing import Any

from app.providers.social.base import (
    CommentPage,
    ContentMetrics,
    NormalizedComment,
    NormalizedContent,
    NormalizedProfile,
    ProviderPage,
)
from app.providers.social.tikhub.xiaohongshu import (
    _first,
    _parse_time,
    _unwrap_data,
    parse_count,
)


def _first_url(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    if not isinstance(value, dict):
        return None
    urls = value.get("url_list")
    if isinstance(urls, list):
        return next((item for item in urls if isinstance(item, str) and item), None)
    return _first(value, "url", "uri")


class DouyinAppV3Adapter:
    platform = "douyin"
    content_domain = "www.douyin.com"
    profile_contents_endpoint_key = "douyin.profile_contents"

    def parse_profile(self, payload: dict[str, Any], *, external_id: str) -> NormalizedProfile:
        body = _unwrap_data(payload)
        raw = body.get("user") or body.get("user_info") or body
        if not isinstance(raw, dict):
            raw = {}
        display_name = _first(raw, "nickname", "display_name", "name")
        if not isinstance(display_name, str) or not display_name.strip():
            raise ValueError("TikHub Douyin profile response is missing nickname")
        avatar = _first_url(
            raw.get("avatar_larger") or raw.get("avatar_medium") or raw.get("avatar_thumb")
        )
        return NormalizedProfile(
            platform=self.platform,
            external_id=external_id,
            display_name=display_name.strip(),
            handle=_first(raw, "unique_id", "short_id"),
            bio=_first(raw, "signature", "bio", "description"),
            avatar_url=avatar,
            followers=parse_count(_first(raw, "follower_count", "followers")),
            following=parse_count(_first(raw, "following_count", "following")),
            total_likes=parse_count(_first(raw, "total_favorited", "aweme_favorite_count")),
            content_count=parse_count(_first(raw, "aweme_count", "content_count")),
        )

    def parse_profile_contents(
        self,
        payload: dict[str, Any],
        *,
        profile_id: str,
    ) -> ProviderPage:
        body = _unwrap_data(payload)
        raw_items = body.get("aweme_list") or body.get("items") or []
        if not isinstance(raw_items, list):
            raise ValueError("TikHub Douyin response has an invalid aweme_list")
        items = [
            item
            for raw in raw_items
            if isinstance(raw, dict)
            and (item := self._parse_content(raw, fallback_external_id=None)) is not None
        ]
        cursor = _first(body, "max_cursor", "cursor", "next_cursor")
        has_more = bool(_first(body, "has_more", "hasMore"))
        return ProviderPage(
            items=items,
            next_cursor=str(cursor) if has_more and cursor not in {None, ""} else None,
            endpoint_key=self.profile_contents_endpoint_key,
            provider_request_id=payload.get("request_id"),
            raw_response=payload,
        )

    def parse_content_detail(
        self,
        payload: dict[str, Any],
        *,
        content_type: str = "video",
        fallback_external_id: str | None = None,
    ) -> NormalizedContent:
        body = _unwrap_data(payload)
        raw = body.get("aweme_detail") or body.get("aweme") or body
        if not isinstance(raw, dict):
            raise ValueError("TikHub Douyin detail response has an invalid shape")
        item = self._parse_content(raw, fallback_external_id=fallback_external_id)
        if item is None:
            raise ValueError("TikHub Douyin detail response is missing aweme_id")
        return item

    def _parse_content(
        self,
        raw: dict[str, Any],
        *,
        fallback_external_id: str | None,
    ) -> NormalizedContent | None:
        aweme_id = _first(raw, "aweme_id", "id") or fallback_external_id
        if not isinstance(aweme_id, str) or not aweme_id:
            return None
        author = raw.get("author") if isinstance(raw.get("author"), dict) else {}
        statistics = raw.get("statistics") if isinstance(raw.get("statistics"), dict) else {}
        images = raw.get("images") or raw.get("image_list") or []
        media: list[dict[str, Any]] = []
        if isinstance(images, list):
            for image in images:
                url = _first_url(image)
                if url:
                    media.append({"type": "image", "url": url})
        video = raw.get("video") if isinstance(raw.get("video"), dict) else {}
        cover_url = _first_url(video.get("cover"))
        play_url = _first_url(video.get("play_addr"))
        if cover_url:
            media.append({"type": "cover", "url": cover_url})
        if play_url:
            media.append({"type": "video", "url": play_url})
        content_type = "image_text" if media and not play_url else "video"
        return NormalizedContent(
            platform=self.platform,
            external_id=aweme_id,
            canonical_url=f"https://{self.content_domain}/video/{aweme_id}",
            content_type=content_type,
            title=None,
            body_text=_first(raw, "desc", "description"),
            published_at=_parse_time(_first(raw, "create_time", "published_at")),
            duration_ms=parse_count(_first(raw, "duration") or _first(video, "duration")),
            author={
                "external_id": _first(author, "sec_uid", "uid", "id"),
                "display_name": _first(author, "nickname", "name"),
                "handle": _first(author, "unique_id", "short_id"),
                "followers": parse_count(_first(author, "follower_count", "followers")),
            },
            metrics=ContentMetrics(
                views=parse_count(_first(statistics, "play_count", "views")),
                likes=parse_count(_first(statistics, "digg_count", "like_count")),
                comments=parse_count(_first(statistics, "comment_count", "comments")),
                favorites=parse_count(_first(statistics, "collect_count", "favorites")),
                shares=parse_count(_first(statistics, "share_count", "shares")),
                downloads=parse_count(_first(statistics, "download_count", "downloads")),
            ),
            media=media,
            provider_metadata={"provider": "tikhub"},
        )

    def parse_comments(self, payload: dict[str, Any]) -> CommentPage:
        body = _unwrap_data(payload)
        raw_items = body.get("comments") or body.get("comment_list") or []
        if not isinstance(raw_items, list):
            raise ValueError("TikHub Douyin response has an invalid comments collection")
        items: list[NormalizedComment] = []
        for raw in raw_items:
            if not isinstance(raw, dict):
                continue
            comment_id = _first(raw, "cid", "comment_id", "id")
            text = _first(raw, "text", "content")
            if not isinstance(comment_id, str) or not isinstance(text, str) or not text.strip():
                continue
            user = raw.get("user") if isinstance(raw.get("user"), dict) else {}
            items.append(
                NormalizedComment(
                    external_id=comment_id,
                    parent_external_id=_first(raw, "reply_id", "reply_to_reply_id"),
                    author={
                        "external_id": _first(user, "sec_uid", "uid", "id"),
                        "display_name": _first(user, "nickname", "name"),
                    },
                    body_text=text.strip(),
                    like_count=parse_count(_first(raw, "digg_count", "like_count")),
                    published_at=_parse_time(_first(raw, "create_time", "published_at")),
                )
            )
        cursor = _first(body, "cursor", "next_cursor")
        has_more = bool(_first(body, "has_more", "hasMore"))
        return CommentPage(
            items=items,
            cursor=str(cursor) if has_more and cursor not in {None, ""} else None,
            index=0,
            page_area="DEFAULT",
            has_more=has_more,
        )


class TikTokAppV3Adapter(DouyinAppV3Adapter):
    platform = "tiktok"
    content_domain = "www.tiktok.com"
    profile_contents_endpoint_key = "tiktok.profile_contents"
