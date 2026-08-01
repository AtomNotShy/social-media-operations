import json
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from app.providers.social.base import (
    CommentPage,
    ContentMetrics,
    NormalizedComment,
    NormalizedContent,
    NormalizedProfile,
    ProviderPage,
    SearchPage,
)


def parse_count(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, float):
        return round(value) if value >= 0 else None
    if not isinstance(value, str):
        return None
    text = value.strip().replace(",", "")
    if not text:
        return None
    multiplier = Decimal(1)
    for suffix, factor in (("万", 10_000), ("w", 10_000), ("W", 10_000), ("亿", 100_000_000)):
        if text.endswith(suffix):
            text = text[: -len(suffix)]
            multiplier = Decimal(factor)
            break
    try:
        parsed = Decimal(text) * multiplier
    except InvalidOperation:
        return None
    return int(parsed) if parsed >= 0 else None


def _unwrap_data(payload: dict[str, Any]) -> dict[str, Any]:
    current: Any = payload
    for _ in range(4):
        if not isinstance(current, dict):
            break
        nested = current.get("data")
        if not isinstance(nested, dict):
            break
        current = nested
    return current if isinstance(current, dict) else {}


def _unwrap_detail_note(body: dict[str, Any]) -> dict[str, Any]:
    note_list = body.get("note_list")
    if isinstance(note_list, list):
        for item in note_list:
            if isinstance(item, dict) and _first(item, "note_id", "id"):
                return item
    data_list = body.get("data")
    if isinstance(data_list, list):
        for wrapper in data_list:
            if not isinstance(wrapper, dict):
                continue
            if _first(wrapper, "note_id", "id") and _first(wrapper, "title", "desc"):
                return wrapper
            nested = wrapper.get("note_list")
            if isinstance(nested, list):
                for item in nested:
                    if isinstance(item, dict) and _first(item, "note_id", "id"):
                        return item
    for key in ("note", "note_info", "item", "note_detail"):
        value = body.get(key)
        if isinstance(value, dict):
            return value
    return body


def _first(mapping: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = mapping.get(key)
        if value is not None and value != "":
            return value
    return None


def _parse_time(value: Any) -> datetime | None:
    if isinstance(value, (int, float)):
        seconds = value / 1000 if value > 10_000_000_000 else value
        try:
            return datetime.fromtimestamp(seconds, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    if isinstance(value, str) and value:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    return None


class XiaohongshuAppV2Adapter:
    platform = "xiaohongshu"

    def parse_profile(
        self,
        payload: dict[str, Any],
        *,
        external_id: str,
    ) -> NormalizedProfile:
        body = _unwrap_data(payload)
        basic = body.get("basic_info") or body.get("user_info") or body.get("user") or body
        if not isinstance(basic, dict):
            basic = {}

        interaction_values: dict[str, Any] = {}
        interactions = body.get("interactions") or basic.get("interactions") or []
        if isinstance(interactions, list):
            for item in interactions:
                if not isinstance(item, dict):
                    continue
                key = str(_first(item, "type", "name", "key") or "").lower()
                interaction_values[key] = _first(item, "count", "value", "num")

        followers = _first(basic, "followers", "fans", "follower_count", "fans_count")
        following = _first(basic, "following", "follows", "following_count")
        total_likes = _first(basic, "liked", "likes", "liked_count", "total_likes")
        content_count = _first(basic, "note_count", "notes", "content_count")
        if content_count is None:
            note_stat = (
                basic.get("note_num_stat") if isinstance(basic.get("note_num_stat"), dict) else None
            )
            if note_stat is not None:
                content_count = _first(note_stat, "posted", "note_count", "count")
        followers = followers if followers is not None else interaction_values.get("fans")
        following = following if following is not None else interaction_values.get("follows")
        total_likes = (
            total_likes
            if total_likes is not None
            else interaction_values.get("interaction") or interaction_values.get("liked")
        )

        display_name = _first(basic, "nickname", "display_name", "name")
        if not isinstance(display_name, str) or not display_name.strip():
            raise ValueError("TikHub profile response is missing nickname")
        avatar = _first(basic, "imageb", "images", "avatar", "avatar_url")
        if isinstance(avatar, list):
            avatar = avatar[0] if avatar else None
        return NormalizedProfile(
            platform=self.platform,
            external_id=external_id,
            display_name=display_name.strip(),
            handle=_first(basic, "red_id", "handle", "username"),
            bio=_first(basic, "desc", "bio", "description"),
            avatar_url=avatar if isinstance(avatar, str) else None,
            followers=parse_count(followers),
            following=parse_count(following),
            total_likes=parse_count(total_likes),
            content_count=parse_count(content_count),
        )

    def parse_profile_contents(
        self,
        payload: dict[str, Any],
        *,
        profile_id: str,
    ) -> ProviderPage:
        body = _unwrap_data(payload)
        raw_items = body.get("notes") or body.get("items") or body.get("note_list") or []
        if not isinstance(raw_items, list):
            raise ValueError("TikHub notes response has an invalid notes collection")
        items: list[NormalizedContent] = []
        last_cursor: str | None = None
        for wrapper in raw_items:
            if not isinstance(wrapper, dict):
                continue
            raw = wrapper.get("note_card") or wrapper.get("note") or wrapper
            if not isinstance(raw, dict):
                continue
            note_id = _first(raw, "note_id", "id")
            if not isinstance(note_id, str) or not note_id:
                continue
            user = raw.get("user") if isinstance(raw.get("user"), dict) else {}
            interaction = (
                raw.get("interact_info")
                if isinstance(raw.get("interact_info"), dict)
                else raw.get("interaction_info")
                if isinstance(raw.get("interaction_info"), dict)
                else {}
            )
            cover = raw.get("cover") if isinstance(raw.get("cover"), dict) else None
            cover_url = _first(cover, "url_default", "url_pre", "url") if cover else None
            if not cover_url:
                for key in ("images_list", "image_list", "images"):
                    candidates = raw.get(key)
                    if not isinstance(candidates, list) or not candidates:
                        continue
                    first = candidates[0]
                    if isinstance(first, dict):
                        cover_url = _first(
                            first,
                            "url_size_large",
                            "url",
                            "url_default",
                            "url_pre",
                        )
                        break
            video_info = (
                raw.get("video_info_v2") if isinstance(raw.get("video_info_v2"), dict) else None
            )
            if not cover_url and video_info is not None:
                image_info = (
                    video_info.get("image") if isinstance(video_info.get("image"), dict) else {}
                )
                cover_url = _first(image_info, "first_frame", "thumbnail", "thumbnail_dim")
            note_type = str(_first(raw, "type", "note_type") or "").lower()
            content_type = "video" if "video" in note_type else "image_text"
            duration_ms = parse_count(_first(raw, "duration_ms", "video_duration"))
            if duration_ms is None and video_info is not None:
                capa = video_info.get("capa") if isinstance(video_info.get("capa"), dict) else {}
                duration_seconds = parse_count(_first(capa, "duration"))
                if duration_seconds is not None:
                    duration_ms = duration_seconds * 1000
            items.append(
                NormalizedContent(
                    platform=self.platform,
                    external_id=note_id,
                    canonical_url=f"https://www.xiaohongshu.com/explore/{note_id}",
                    content_type=content_type,
                    title=_first(raw, "display_title", "title"),
                    body_text=_first(raw, "desc", "description", "body_text"),
                    published_at=_parse_time(_first(raw, "time", "create_time", "published_at")),
                    duration_ms=duration_ms,
                    author={
                        "external_id": _first(user, "user_id", "userid", "id") or profile_id,
                        "display_name": _first(user, "nickname", "name"),
                        "handle": _first(user, "red_id", "username"),
                    },
                    metrics=ContentMetrics(
                        views=parse_count(
                            _first(interaction, "view_count", "views")
                            or _first(raw, "view_count", "views")
                        ),
                        likes=parse_count(
                            _first(interaction, "liked_count", "likes", "like_count")
                            or _first(raw, "likes", "like_count")
                        ),
                        comments=parse_count(
                            _first(interaction, "comment_count", "comments")
                            or _first(raw, "comments_count", "comment_count", "comments")
                        ),
                        favorites=parse_count(
                            _first(
                                interaction,
                                "collected_count",
                                "collect_count",
                                "favorites",
                            )
                            or _first(raw, "collected_count", "collect_count")
                        ),
                        shares=parse_count(
                            _first(interaction, "share_count", "shares")
                            or _first(raw, "share_count", "shares")
                        ),
                    ),
                    media=[{"type": "cover", "url": cover_url}] if cover_url else [],
                    provider_metadata={"provider": "tikhub"},
                )
            )
            cursor = _first(wrapper, "cursor") or _first(raw, "cursor")
            last_cursor = str(cursor or note_id)
        body_cursor = _first(body, "cursor", "next_cursor")
        next_cursor = str(body_cursor) if body_cursor not in {None, ""} else last_cursor
        return ProviderPage(
            items=items,
            next_cursor=next_cursor,
            endpoint_key="xhs.profile_contents",
            provider_request_id=payload.get("request_id"),
            raw_response=payload,
        )

    def parse_content_detail(
        self,
        payload: dict[str, Any],
        *,
        content_type: str,
        fallback_external_id: str | None = None,
    ) -> NormalizedContent:
        body = _unwrap_data(payload)
        raw = _unwrap_detail_note(body)
        if not isinstance(raw, dict):
            raise ValueError("TikHub note detail response has an invalid shape")
        note_id = _first(raw, "note_id", "id") or fallback_external_id
        if not isinstance(note_id, str) or not note_id:
            raise ValueError("TikHub note detail response is missing note_id")

        user = raw.get("user") if isinstance(raw.get("user"), dict) else {}
        interaction = (
            raw.get("interact_info")
            if isinstance(raw.get("interact_info"), dict)
            else raw.get("interaction_info")
            if isinstance(raw.get("interaction_info"), dict)
            else {}
        )
        media: list[dict[str, Any]] = []
        images = raw.get("image_list") or raw.get("images_list") or raw.get("images") or []
        if isinstance(images, list):
            for image in images:
                if isinstance(image, str):
                    media.append({"type": "image", "url": image})
                elif isinstance(image, dict):
                    url = _first(
                        image,
                        "url_size_large",
                        "url_default",
                        "url_pre",
                        "original",
                        "url",
                    )
                    if isinstance(url, str):
                        media.append({"type": "image", "url": url})
        video = raw.get("video") if isinstance(raw.get("video"), dict) else {}
        video_url = _first(video, "master_url", "url", "play_url")
        if isinstance(video_url, str):
            media.append({"type": "video", "url": video_url})
        cover = raw.get("cover") if isinstance(raw.get("cover"), dict) else {}
        cover_url = _first(cover, "url_default", "url_pre", "url")
        if isinstance(cover_url, str):
            media.append({"type": "cover", "url": cover_url})
        video_info = (
            raw.get("video_info_v2") if isinstance(raw.get("video_info_v2"), dict) else None
        )
        if video_info is not None:
            media_info = (
                video_info.get("media") if isinstance(video_info.get("media"), dict) else {}
            )
            streams = media_info.get("stream") if isinstance(media_info.get("stream"), dict) else {}
            master_url = None
            for codec in ("h264", "h265", "av1"):
                variants = streams.get(codec)
                if not isinstance(variants, list) or not variants:
                    continue
                first = variants[0]
                if isinstance(first, dict) and isinstance(first.get("master_url"), str):
                    master_url = first["master_url"]
                    break
            if master_url:
                media.append({"type": "video", "url": master_url})
            image_info = (
                video_info.get("image") if isinstance(video_info.get("image"), dict) else {}
            )
            video_cover = _first(image_info, "first_frame", "thumbnail", "thumbnail_dim")
            if isinstance(video_cover, str):
                media.append({"type": "cover", "url": video_cover})

        duration_ms = parse_count(_first(raw, "duration_ms"))
        if duration_ms is None and video_info is not None:
            capa = video_info.get("capa") if isinstance(video_info.get("capa"), dict) else {}
            duration_seconds = parse_count(_first(capa, "duration"))
            if duration_seconds is not None:
                duration_ms = duration_seconds * 1000
        return NormalizedContent(
            platform=self.platform,
            external_id=note_id,
            canonical_url=f"https://www.xiaohongshu.com/explore/{note_id}",
            content_type=content_type,
            title=_first(raw, "title", "display_title"),
            body_text=_first(raw, "desc", "description", "body_text"),
            published_at=_parse_time(_first(raw, "time", "create_time", "published_at")),
            duration_ms=duration_ms,
            author={
                "external_id": _first(user, "user_id", "userid", "id"),
                "display_name": _first(user, "nickname", "name"),
                "handle": _first(user, "red_id", "username"),
                "followers": parse_count(_first(user, "followers", "fans", "follower_count")),
            },
            metrics=ContentMetrics(
                views=parse_count(
                    _first(interaction, "view_count", "views") or _first(raw, "view_count", "views")
                ),
                likes=parse_count(
                    _first(interaction, "liked_count", "likes", "like_count")
                    or _first(raw, "liked_count", "likes", "like_count")
                ),
                comments=parse_count(
                    _first(interaction, "comment_count", "comments")
                    or _first(raw, "comments_count", "comment_count", "comments")
                ),
                favorites=parse_count(
                    _first(
                        interaction,
                        "collected_count",
                        "collect_count",
                        "favorites",
                    )
                    or _first(raw, "collected_count", "collect_count")
                ),
                shares=parse_count(
                    _first(interaction, "share_count", "shares")
                    or _first(raw, "shared_count", "share_count", "shares")
                ),
            ),
            media=media,
            provider_metadata={
                "provider": "tikhub",
                "provider_request_id": payload.get("request_id"),
            },
        )

    def parse_comments(self, payload: dict[str, Any]) -> CommentPage:
        body = _unwrap_data(payload)
        raw_items = body.get("comments") or body.get("comment_list") or body.get("items") or []
        if not isinstance(raw_items, list):
            raise ValueError("TikHub comments response has an invalid comments collection")
        items: list[NormalizedComment] = []
        for raw in raw_items:
            if not isinstance(raw, dict):
                continue
            parsed = self._parse_comment(raw, parent_external_id=None)
            if parsed is not None:
                items.append(parsed)
            sub_comments = raw.get("sub_comments")
            if isinstance(sub_comments, list):
                parent_id = _first(raw, "comment_id", "id")
                for sub in sub_comments:
                    if isinstance(sub, dict):
                        parsed_sub = self._parse_comment(sub, parent_external_id=parent_id)
                        if parsed_sub is not None:
                            items.append(parsed_sub)
        cursor_data = body.get("cursor")
        if isinstance(cursor_data, dict):
            cursor = _first(cursor_data, "cursor", "id")
            index_value = _first(cursor_data, "index", "page_index")
            page_area = _first(cursor_data, "pageArea", "page_area")
        elif isinstance(cursor_data, str) and cursor_data.strip().startswith("{"):
            try:
                parsed_cursor = json.loads(cursor_data)
            except json.JSONDecodeError:
                parsed_cursor = None
            if isinstance(parsed_cursor, dict):
                cursor = _first(parsed_cursor, "cursor", "id") or cursor_data
                index_value = _first(parsed_cursor, "index", "page_index")
                page_area = _first(parsed_cursor, "pageArea", "page_area")
            else:
                cursor = cursor_data
                index_value = None
                page_area = None
        else:
            cursor = cursor_data or _first(body, "next_cursor")
            index_value = _first(body, "index", "page_index")
            page_area = _first(body, "pageArea", "page_area")
        has_more_value = _first(body, "has_more", "hasMore")
        return CommentPage(
            items=items,
            cursor=str(cursor) if cursor not in {None, ""} else None,
            index=parse_count(index_value) or 0,
            page_area=str(page_area or "UNFOLDED"),
            has_more=bool(has_more_value) if has_more_value is not None else bool(cursor),
        )

    @staticmethod
    def _parse_comment(
        raw: dict[str, Any],
        *,
        parent_external_id: str | None,
    ) -> NormalizedComment | None:
        comment_id = _first(raw, "comment_id", "id")
        text = _first(raw, "content", "text", "body_text")
        if not isinstance(comment_id, str) or not comment_id:
            return None
        if not isinstance(text, str) or not text.strip():
            return None
        user = (
            raw.get("user_info")
            if isinstance(raw.get("user_info"), dict)
            else raw.get("user")
            if isinstance(raw.get("user"), dict)
            else {}
        )
        return NormalizedComment(
            external_id=comment_id,
            parent_external_id=_first(
                raw,
                "parent_comment_id",
                "parent_id",
                "target_comment_id",
            )
            or parent_external_id,
            author={
                "external_id": _first(user, "user_id", "userid", "id"),
                "display_name": _first(user, "nickname", "name"),
                "handle": _first(user, "red_id", "username"),
            },
            body_text=text.strip(),
            like_count=parse_count(_first(raw, "like_count", "liked_count", "likes")),
            published_at=_parse_time(_first(raw, "create_time", "time", "published_at")),
        )

    def parse_search_results(self, payload: dict[str, Any]) -> SearchPage:
        page = self.parse_profile_contents(payload, profile_id="search-result")
        body = _unwrap_data(payload)
        search_id = _first(body, "search_id", "searchId")
        search_session_id = _first(body, "search_session_id", "searchSessionId")
        has_more_value = _first(body, "has_more", "hasMore")
        return SearchPage(
            items=page.items,
            search_id=str(search_id) if search_id not in {None, ""} else None,
            search_session_id=(
                str(search_session_id) if search_session_id not in {None, ""} else None
            ),
            has_more=(bool(has_more_value) if has_more_value is not None else bool(page.items)),
        )
