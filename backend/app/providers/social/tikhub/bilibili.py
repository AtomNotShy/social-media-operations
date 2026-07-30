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


def _image_url(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    if not isinstance(value, dict):
        return None
    return _first(value, "url", "src")


class BilibiliAdapter:
    platform = "bilibili"

    def parse_profile(self, payload: dict[str, Any], *, external_id: str) -> NormalizedProfile:
        body = _unwrap_data(payload)
        raw = body.get("card") or body.get("user") or body
        if not isinstance(raw, dict):
            raw = {}
        display_name = _first(raw, "name", "nickname", "uname")
        if not isinstance(display_name, str) or not display_name.strip():
            raise ValueError("TikHub Bilibili profile response is missing name")
        stats = body.get("stats") if isinstance(body.get("stats"), dict) else body
        return NormalizedProfile(
            platform=self.platform,
            external_id=external_id,
            display_name=display_name.strip(),
            handle=str(_first(raw, "mid", "uid") or external_id),
            bio=_first(raw, "sign", "bio", "description"),
            avatar_url=_image_url(_first(raw, "face", "avatar")),
            followers=parse_count(_first(stats, "follower", "fans", "follower_count")),
            following=parse_count(_first(stats, "following", "follow", "following_count")),
            total_likes=parse_count(_first(stats, "likes", "total_likes")),
            content_count=parse_count(_first(stats, "archive_count", "video_count", "videos")),
        )

    def parse_profile_contents(
        self,
        payload: dict[str, Any],
        *,
        profile_id: str,
    ) -> ProviderPage:
        body = _unwrap_data(payload)
        list_body = body.get("list") if isinstance(body.get("list"), dict) else body
        raw_items = (
            list_body.get("vlist")
            or list_body.get("items")
            or body.get("item")
            or body.get("archives")
            or []
        )
        if not isinstance(raw_items, list):
            raise ValueError("TikHub Bilibili response has an invalid video collection")
        items = [
            item
            for raw in raw_items
            if isinstance(raw, dict) and (item := self._parse_content(raw)) is not None
        ]
        page = body.get("page") if isinstance(body.get("page"), dict) else {}
        current_page = parse_count(_first(page, "pn", "page")) or 1
        page_size = parse_count(_first(page, "ps", "page_size")) or max(len(items), 1)
        total = parse_count(_first(page, "count", "total"))
        has_more = total is not None and current_page * page_size < total
        return ProviderPage(
            items=items,
            next_cursor=str(current_page + 1) if has_more else None,
            endpoint_key="bilibili.profile_contents",
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
        raw = body.get("View") or body.get("view") or body.get("archive") or body
        if not isinstance(raw, dict):
            raise ValueError("TikHub Bilibili detail response has an invalid shape")
        item = self._parse_content(raw, fallback_external_id=fallback_external_id)
        if item is None:
            raise ValueError("TikHub Bilibili detail response is missing bvid")
        return item

    def _parse_content(
        self,
        raw: dict[str, Any],
        *,
        fallback_external_id: str | None = None,
    ) -> NormalizedContent | None:
        bvid = _first(raw, "bvid", "bv_id") or fallback_external_id
        aid = _first(raw, "aid", "av_id")
        external_id = str(bvid or aid or "")
        if not external_id:
            return None
        owner = raw.get("owner") if isinstance(raw.get("owner"), dict) else {}
        stat = raw.get("stat") if isinstance(raw.get("stat"), dict) else raw
        cover = _image_url(_first(raw, "pic", "cover"))
        return NormalizedContent(
            platform=self.platform,
            external_id=external_id,
            canonical_url=f"https://www.bilibili.com/video/{external_id}",
            content_type="video",
            title=_first(raw, "title", "name"),
            body_text=_first(raw, "desc", "description"),
            published_at=_parse_time(_first(raw, "pubdate", "created", "ctime")),
            duration_ms=(
                parse_count(_first(raw, "duration")) * 1000
                if parse_count(_first(raw, "duration")) is not None
                else None
            ),
            author={
                "external_id": _first(owner, "mid", "uid") or _first(raw, "mid"),
                "display_name": _first(owner, "name", "uname") or _first(raw, "author"),
                "handle": _first(owner, "mid", "uid"),
            },
            metrics=ContentMetrics(
                views=parse_count(_first(stat, "view", "play", "views")),
                likes=parse_count(_first(stat, "like", "likes")),
                comments=parse_count(_first(stat, "reply", "comment", "comments")),
                favorites=parse_count(_first(stat, "favorite", "favorites")),
                shares=parse_count(_first(stat, "share", "shares")),
            ),
            media=[{"type": "cover", "url": cover}] if cover else [],
            provider_metadata={"provider": "tikhub", "aid": aid},
        )

    def parse_comments(self, payload: dict[str, Any]) -> CommentPage:
        body = _unwrap_data(payload)
        raw_items = body.get("replies") or body.get("items") or []
        if not isinstance(raw_items, list):
            raise ValueError("TikHub Bilibili response has an invalid replies collection")
        items: list[NormalizedComment] = []
        for raw in raw_items:
            if not isinstance(raw, dict):
                continue
            comment_id = _first(raw, "rpid_str", "rpid", "id")
            content = raw.get("content") if isinstance(raw.get("content"), dict) else {}
            text = _first(content, "message", "text") or _first(raw, "message", "text")
            if comment_id in {None, ""} or not isinstance(text, str) or not text.strip():
                continue
            member = raw.get("member") if isinstance(raw.get("member"), dict) else {}
            items.append(
                NormalizedComment(
                    external_id=str(comment_id),
                    parent_external_id=(
                        str(parent)
                        if (parent := _first(raw, "parent_str", "parent")) not in {None, "0", 0}
                        else None
                    ),
                    author={
                        "external_id": _first(member, "mid", "uid"),
                        "display_name": _first(member, "uname", "name"),
                    },
                    body_text=text.strip(),
                    like_count=parse_count(_first(raw, "like", "like_count")),
                    published_at=_parse_time(_first(raw, "ctime", "create_time")),
                )
            )
        cursor_body = body.get("cursor") if isinstance(body.get("cursor"), dict) else {}
        cursor = _first(cursor_body, "next", "pagination_reply", "offset")
        has_more = not bool(_first(cursor_body, "is_end")) if cursor_body else False
        return CommentPage(
            items=items,
            cursor=str(cursor) if has_more and cursor not in {None, ""} else None,
            index=0,
            page_area="DEFAULT",
            has_more=has_more,
        )
