from datetime import datetime, timezone
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

_TWITTER_TIME_FORMATS = (
    "%a %b %d %H:%M:%S %z %Y",
    "%a %b %d %H:%M:%S %Z %Y",
)


def _parse_twitter_time(value: Any) -> datetime | None:
    if isinstance(value, str) and value:
        stripped = value.strip()
        for fmt in _TWITTER_TIME_FORMATS:
            try:
                parsed = datetime.strptime(stripped, fmt)
            except ValueError:
                continue
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        if stripped.isdigit():
            return _parse_time(int(stripped))
        return _parse_time(stripped)
    return _parse_time(value)


def _author_dict(raw: dict[str, Any]) -> dict[str, Any]:
    author = raw.get("author") if isinstance(raw.get("author"), dict) else {}
    if not author:
        core = raw.get("core") if isinstance(raw.get("core"), dict) else None
        if core is not None:
            user_results = (
                core.get("user_results") if isinstance(core.get("user_results"), dict) else None
            )
            if user_results is not None:
                nested = (
                    user_results.get("result")
                    if isinstance(user_results.get("result"), dict)
                    else None
                )
                if isinstance(nested, dict):
                    author = (
                        nested.get("legacy") if isinstance(nested.get("legacy"), dict) else nested
                    )
    return {
        "external_id": _first(author, "rest_id", "id_str", "id"),
        "display_name": _first(author, "name"),
        "handle": _first(author, "screen_name", "profile"),
        "followers": parse_count(_first(author, "followers_count", "sub_count")),
    }


def _media_items(raw: dict[str, Any]) -> list[dict[str, Any]]:
    media: list[dict[str, Any]] = []
    seen: set[Any] = set()
    for item in _collect_media_items(raw):
        identity = _first(item, "id", "id_str", "media_id")
        if identity is None:
            identity = _first(item, "media_url_https", "expanded_url")
        if identity is not None:
            if identity in seen:
                continue
            seen.add(identity)
        media_type = _first(item, "type")
        if not isinstance(media_type, str) or media_type not in {"video", "animated_gif", "photo"}:
            media_type = "photo"
        video_info = item.get("video_info") if isinstance(item.get("video_info"), dict) else None
        variants = item.get("variants") if isinstance(item.get("variants"), list) else None
        if variants is None and video_info is not None:
            nested = video_info.get("variants")
            variants = nested if isinstance(nested, list) else None
        mp4_url = None
        if isinstance(variants, list):
            mp4 = [
                variant
                for variant in variants
                if isinstance(variant, dict)
                and variant.get("content_type") == "video/mp4"
                and isinstance(variant.get("url"), str)
            ]
            if mp4:
                mp4.sort(key=lambda variant: variant.get("bitrate") or 0)
                mp4_url = mp4[-1]["url"]
        thumb = _first(item, "media_url_https", "media_url", "expanded_url")
        duration = parse_count(_first(video_info or {}, "duration_millis", "duration"))
        if duration is None:
            duration = parse_count(_first(item, "duration_millis", "duration"))
        if media_type in {"video", "animated_gif"}:
            if isinstance(mp4_url, str) and mp4_url:
                media.append({"type": media_type, "url": mp4_url})
                if isinstance(thumb, str) and thumb:
                    media.append({"type": "cover", "url": thumb})
            elif isinstance(thumb, str) and thumb:
                media.append({"type": media_type, "url": thumb})
            if duration is not None and media and media[-1].get("type") == media_type:
                media[-1]["duration_ms"] = duration
        elif isinstance(thumb, str) and thumb:
            media.append({"type": media_type, "url": thumb})
    return media


def _collect_media_items(raw: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    raw_media = raw.get("media")
    if isinstance(raw_media, list):
        items.extend(item for item in raw_media if isinstance(item, dict))
    elif isinstance(raw_media, dict):
        for media_type, group in raw_media.items():
            if not isinstance(group, list):
                continue
            for item in group:
                if not isinstance(item, dict):
                    continue
                if "type" not in item:
                    item = {**item, "type": media_type}
                items.append(item)
    entities = raw.get("entities") if isinstance(raw.get("entities"), dict) else None
    legacy_media = entities.get("media") if entities is not None else None
    if isinstance(legacy_media, list):
        items.extend(item for item in legacy_media if isinstance(item, dict))
    return items


def _tweet_external_id(raw: dict[str, Any], fallback: str | None) -> str | None:
    value = _first(raw, "tweet_id", "id_str", "rest_id", "id")
    if isinstance(value, str) and value:
        return value
    if isinstance(value, int) and value > 0:
        return str(value)
    return fallback


def _article_cover_url(article: dict[str, Any]) -> str | None:
    cover = article.get("cover_media")
    if isinstance(cover, str) and cover.strip():
        return cover.strip()
    if isinstance(cover, dict):
        value = _first(cover, "url", "media_url_https", "media_url")
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _tweet_entities(raw: dict[str, Any]) -> dict[str, Any]:
    entities = raw.get("entities") if isinstance(raw.get("entities"), dict) else None
    if entities is None:
        note = raw.get("note") if isinstance(raw.get("note"), dict) else None
        if note is not None:
            entities = (
                note.get("entities")
                if isinstance(note.get("entities"), dict)
                else None
            )
    if entities is None:
        entities = {}
    return {
        "urls": entities.get("urls") if isinstance(entities.get("urls"), list) else [],
        "media": entities.get("media") if isinstance(entities.get("media"), list) else [],
        "mentions": (
            entities.get("user_mentions")
            if isinstance(entities.get("user_mentions"), list)
            else entities.get("mentions")
            if isinstance(entities.get("mentions"), list)
            else []
        ),
        "hashtags": entities.get("hashtags") if isinstance(entities.get("hashtags"), list) else [],
    }


def _tweet_entity_items(
    entities: dict[str, Any],
) -> list[tuple[str, dict[str, Any]]]:
    """Collect entity entries with a stable key used for replacement."""
    items: list[tuple[str, dict[str, Any]]] = []
    for entry in entities.get("urls", []):
        if isinstance(entry, dict):
            items.append(("url", entry))
    for entry in entities.get("media", []):
        if isinstance(entry, dict):
            items.append(("media", entry))
    for entry in entities.get("mentions", []):
        if isinstance(entry, dict):
            items.append(("mention", entry))
    for entry in entities.get("hashtags", []):
        if isinstance(entry, dict):
            items.append(("hashtag", entry))
    return items


def _entity_range(entry: dict[str, Any]) -> list[int] | None:
    indices = entry.get("indices")
    if isinstance(indices, list) and len(indices) >= 2:
        start, end = indices[0], indices[1]
        if isinstance(start, int) and isinstance(end, int) and 0 <= start < end:
            return [start, end]
    return None


def _tweet_runs(text: str, entities: dict[str, Any]) -> list[dict[str, Any]]:
    """Reconstruct the tweet text as styled runs, expanding short links."""
    if not isinstance(text, str) or not text.strip():
        return []
    items = [
        (kind, entry, _entity_range(entry))
        for kind, entry in _tweet_entity_items(entities)
    ]
    ranged = sorted(
        (
            (start, end, kind, entry)
            for kind, entry, indices in items
            if indices
            for start, end in [indices]
        ),
        key=lambda item: (item[0], item[1]),
    )
    cursor = 0
    runs: list[dict[str, Any]] = []
    for start, end, kind, entry in ranged:
        if start < cursor or start >= len(text):
            continue
        if start > cursor:
            runs.append({"text": text[cursor:start], "style": "text"})
        runs.append(_tweet_entity_run(kind, entry))
        cursor = end
    if cursor < len(text):
        runs.append({"text": text[cursor:], "style": "text"})

    for kind, entry, indices in items:
        if indices is not None:
            continue
        needle = _entity_needle(kind, entry)
        if not needle:
            continue
        runs = _replace_run_text(runs, needle, _tweet_entity_run(kind, entry))

    merged: list[dict[str, Any]] = []
    for run in runs:
        if not isinstance(run.get("text"), str) or run["text"] == "":
            continue
        if merged and merged[-1].get("style") == run.get("style") == "text":
            merged[-1]["text"] += run["text"]
        else:
            merged.append(dict(run))
    return merged


def _replace_run_text(
    runs: list[dict[str, Any]],
    needle: str,
    replacement: dict[str, Any],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for run in runs:
        text = run.get("text")
        if not isinstance(text, str) or not needle or needle not in text:
            out.append(run)
            continue
        head, _, tail = text.partition(needle)
        if head:
            out.append({"text": head, "style": "text"})
        out.append(replacement)
        if tail:
            out.append({"text": tail, "style": "text"})
    return out


def _tweet_entity_run(kind: str, entry: dict[str, Any]) -> dict[str, Any]:
    if kind == "url":
        url = _first(entry, "expanded_url", "url")
        if not isinstance(url, str) or not url:
            url = _first(entry, "url", "expanded_url")
        return {"text": str(url or ""), "style": "url", "url": str(url) if url else None}
    if kind == "media":
        media_type = str(_first(entry, "type") or "photo").lower()
        label = {"video": "[视频]", "animated_gif": "[动图]"}.get(media_type, "[图片]")
        return {"text": label, "style": "media_placeholder"}
    if kind == "mention":
        screen_name = _first(entry, "screen_name", "username", "name")
        text = f"@{screen_name}" if isinstance(screen_name, str) and screen_name else "@用户"
        return {"text": text, "style": "mention"}
    if kind == "hashtag":
        tag = _first(entry, "text", "tag")
        text = f"#{tag}" if isinstance(tag, str) and tag else "#话题"
        return {"text": text, "style": "hashtag"}
    return {"text": str(_first(entry, "text") or ""), "style": "text"}


def _entity_needle(kind: str, entry: dict[str, Any]) -> str | None:
    if kind in {"url", "media"}:
        url = _first(entry, "url")
        return url if isinstance(url, str) and url else None
    if kind == "mention":
        screen_name = _first(entry, "screen_name", "username", "name")
        return f"@{screen_name}" if isinstance(screen_name, str) and screen_name else None
    if kind == "hashtag":
        tag = _first(entry, "text", "tag")
        return f"#{tag}" if isinstance(tag, str) and tag else None
    return None


def _quote_block(raw: dict[str, Any]) -> dict[str, Any] | None:
    quote = None
    for key in ("quoted_tweet", "quoted_status", "quote"):
        candidate = raw.get(key)
        if isinstance(candidate, dict):
            quote = candidate
            break
    if quote is None:
        return None
    text = _first(quote, "full_text", "text", "body_text")
    if not isinstance(text, str) or not text.strip():
        return None
    author = _author_dict(quote)
    handle = author.get("handle") or "i"
    tweet_id = _tweet_external_id(quote, None)
    cover_url = None
    for entry in _media_items(quote):
        if entry.get("type") in {"photo", "image", "cover"}:
            cover_url = entry.get("url")
            break
        if entry.get("type") == "video":
            cover_url = entry.get("url")
    return {
        "type": "quote",
        "text": text.strip(),
        "author": {
            "display_name": author.get("display_name"),
            "handle": handle,
        },
        "url": f"https://x.com/{handle}/status/{tweet_id}" if tweet_id else None,
        "media_url": cover_url,
    }


def _tweet_original_content(
    raw: dict[str, Any],
    *,
    text: str | None,
    media: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if not isinstance(text, str) or not text.strip():
        return None
    entities = _tweet_entities(raw)
    runs = _tweet_runs(text, entities)
    blocks: list[dict[str, Any]] = []
    if runs:
        blocks.append({"type": "paragraph", "runs": runs})
    covers = [
        entry["url"]
        for entry in media
        if entry.get("type") == "cover" and isinstance(entry.get("url"), str)
    ]
    for entry in media:
        entry_type = entry.get("type")
        if entry_type == "cover":
            continue
        if entry_type in {"photo", "image"}:
            blocks.append({"type": "image", "url": entry.get("url")})
        elif entry_type in {"video", "animated_gif"}:
            blocks.append(
                {
                    "type": "video",
                    "url": entry.get("url"),
                    "cover_url": covers.pop(0) if covers else None,
                    "duration_ms": entry.get("duration_ms"),
                    "animated": entry_type == "animated_gif",
                }
            )
    quote = _quote_block(raw)
    if quote is not None:
        blocks.append(quote)
    if not blocks:
        return None
    return {"format": "x", "blocks": blocks}


def _parse_tweet(
    raw: dict[str, Any], *, fallback_external_id: str | None = None
) -> NormalizedContent | None:
    if not isinstance(raw, dict):
        return None
    retweeted = raw.get("retweeted_tweet") if isinstance(raw.get("retweeted_tweet"), dict) else None
    merged = raw
    if retweeted is not None:
        merged = {**retweeted, **{k: v for k, v in raw.items() if v not in (None, "", [])}}
    tweet_id = _tweet_external_id(merged, fallback_external_id)
    if not tweet_id:
        return None
    author = _author_dict(merged)
    article = merged.get("article") if isinstance(merged.get("article"), dict) else None
    article_title = _first(article or {}, "title")
    article_text = _first(article or {}, "full_text", "preview_text")
    has_article_title = isinstance(article_title, str) and bool(article_title.strip())
    has_article_text = isinstance(article_text, str) and bool(article_text.strip())
    is_article = article is not None and (has_article_title or has_article_text)
    text = (
        article_text
        if is_article
        else _first(merged, "full_text", "text", "body_text")
    )
    title = (
        article_title.strip()
        if isinstance(article_title, str) and article_title.strip()
        else None
    )
    handle = author.get("handle") or "i"
    media = _media_items(merged)
    cover_url = _article_cover_url(article) if article is not None else None
    if cover_url and not any(entry.get("url") == cover_url for entry in media):
        media.append({"type": "cover", "url": cover_url})
    duration_ms = parse_count(_first(merged, "duration_ms", "duration_millis"))
    if duration_ms is None:
        for entry in media:
            if (
                entry.get("type") in {"video", "animated_gif"}
                and entry.get("duration_ms") is not None
            ):
                duration_ms = entry["duration_ms"]
                break
    return NormalizedContent(
        platform="x",
        external_id=tweet_id,
        canonical_url=f"https://x.com/{handle}/status/{tweet_id}",
        content_type="article" if is_article else "tweet",
        title=title,
        body_text=text,
        published_at=_parse_twitter_time(_first(merged, "created_at")),
        duration_ms=duration_ms,
        author=author,
        metrics=ContentMetrics(
            views=parse_count(_first(merged, "views", "view_count")),
            likes=parse_count(_first(merged, "likes", "favorites", "favorite_count", "like_count")),
            comments=parse_count(_first(merged, "replies", "reply_count", "comments")),
            favorites=parse_count(_first(merged, "bookmarks", "bookmark_count")),
            shares=parse_count(_first(merged, "retweets", "retweet_count")),
        ),
        media=media,
        original_content=_tweet_original_content(
            merged,
            text=text,
            media=media,
        ),
        provider_metadata={
            "provider": "tikhub",
            "conversation_id": _first(merged, "conversation_id"),
            "lang": _first(merged, "lang"),
            "source": _first(merged, "source"),
            "quotes": parse_count(_first(merged, "quotes", "quote_count")),
            "bookmarks": parse_count(_first(merged, "bookmarks", "bookmark_count")),
            "retweeted_id": _first(retweeted, "tweet_id") if retweeted else None,
        },
    )


def _tweet_list(value: Any) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    if not isinstance(value, list):
        return items
    for entry in value:
        if isinstance(entry, dict) and _tweet_external_id(entry, None):
            items.append(entry)
    return items


def _cursor(body: dict[str, Any]) -> str | None:
    value = _first(body, "next_cursor", "cursor", "bottom_cursor")
    return str(value) if value not in {None, ""} else None


class TwitterAdapter:
    platform = "x"

    def parse_profile(self, payload: dict[str, Any], *, external_id: str) -> NormalizedProfile:
        body = _unwrap_data(payload)
        raw = _find_user_result(body)
        legacy = raw.get("legacy") if isinstance(raw.get("legacy"), dict) else {}
        source = legacy or raw
        display_name = _first(source, "name")
        if not isinstance(display_name, str) or not display_name.strip():
            raise ValueError("TikHub X profile response is missing name")
        rest_id = _first(raw, "rest_id", "id", "id_str")
        handle = _first(source, "screen_name", "profile", "username")
        return NormalizedProfile(
            platform=self.platform,
            external_id=external_id,
            display_name=display_name.strip(),
            handle=str(handle) if handle else None,
            bio=_first(source, "description", "desc", "bio"),
            avatar_url=_first(source, "profile_image_url_https", "profile_image_url", "avatar"),
            followers=parse_count(_first(source, "followers_count", "sub_count", "followers")),
            following=parse_count(_first(source, "friends_count", "friends", "following")),
            total_likes=parse_count(_first(source, "favourites_count", "favorites_count")),
            content_count=parse_count(_first(source, "statuses_count", "tweet_count")),
            extra_metrics={
                "rest_id": str(rest_id) if rest_id is not None else None,
                "media_count": parse_count(_first(source, "media_count")),
                "location": _first(source, "location"),
                "created_at": _first(source, "created_at"),
                "protected": source.get("protected"),
                "verified": source.get("verified"),
                "blue_verified": (
                    raw.get("blue_verified")
                    or raw.get("is_blue_verified")
                    or source.get("blue_verified")
                    or source.get("is_blue_verified")
                ),
                "verification_type": _first(source, "verification_type"),
            },
        )

    def parse_profile_contents(
        self,
        payload: dict[str, Any],
        *,
        profile_id: str,
    ) -> ProviderPage:
        body = _unwrap_data(payload)
        items: list[dict[str, Any]] = []
        pinned = body.get("pinned") if isinstance(body.get("pinned"), dict) else None
        if pinned is not None and _tweet_external_id(pinned, None):
            items.append(pinned)
        items.extend(_tweet_list(body.get("timeline")))
        items.extend(_tweet_list(body.get("tweets")))
        items.extend(_tweet_list(body.get("items")))
        if not items:
            items = _graphql_tweet_entries(body)
        parsed = [item for raw in items if (item := _parse_tweet(raw)) is not None]
        cursor = _cursor(body)
        return ProviderPage(
            items=parsed,
            next_cursor=cursor,
            endpoint_key="x.profile_contents",
            provider_request_id=payload.get("request_id"),
            raw_response=payload,
        )

    def parse_content_detail(
        self,
        payload: dict[str, Any],
        *,
        content_type: str = "tweet",
        fallback_external_id: str | None = None,
    ) -> NormalizedContent:
        body = _unwrap_data(payload)
        raw = _unwrap_tweet(body)
        item = _parse_tweet(raw, fallback_external_id=fallback_external_id)
        if item is None:
            raise ValueError("TikHub X detail response is missing tweet_id")
        if content_type and content_type != "tweet":
            item = NormalizedContent(
                platform=item.platform,
                external_id=item.external_id,
                canonical_url=item.canonical_url,
                content_type=content_type,
                title=item.title,
                body_text=item.body_text,
                published_at=item.published_at,
                duration_ms=item.duration_ms,
                author=item.author,
                metrics=item.metrics,
                media=item.media,
                provider_metadata=item.provider_metadata,
            )
        return item

    def parse_comments(self, payload: dict[str, Any]) -> CommentPage:
        body = _unwrap_data(payload)
        items: list[dict[str, Any]] = []
        for key in ("thread", "comments", "replies", "timeline", "items"):
            items.extend(_tweet_list(body.get(key)))
        comments: list[NormalizedComment] = []
        for raw in items:
            tweet_id = _tweet_external_id(raw, None)
            if not tweet_id:
                continue
            author = _author_dict(raw)
            text = _first(raw, "full_text", "text", "body_text")
            if not isinstance(text, str) or not text.strip():
                continue
            comments.append(
                NormalizedComment(
                    external_id=tweet_id,
                    parent_external_id=_first(
                        raw,
                        "in_reply_to_status_id_str",
                        "in_reply_to_status_id",
                        "reply_to",
                        "conversation_id",
                    ),
                    author=author,
                    body_text=text.strip(),
                    like_count=parse_count(
                        _first(raw, "likes", "favorites", "favorite_count", "like_count")
                    ),
                    published_at=_parse_twitter_time(_first(raw, "created_at")),
                )
            )
        cursor = _cursor(body)
        has_more = bool(cursor)
        return CommentPage(
            items=comments,
            cursor=cursor,
            index=0,
            page_area="DEFAULT",
            has_more=has_more,
        )


def _find_user_result(body: dict[str, Any]) -> dict[str, Any]:
    user = body.get("user") if isinstance(body.get("user"), dict) else None
    if user is not None:
        result = user.get("result") if isinstance(user.get("result"), dict) else None
        if result is not None:
            core = result.get("core") if isinstance(result.get("core"), dict) else None
            if core is not None:
                user_results = (
                    core.get("user_results") if isinstance(core.get("user_results"), dict) else None
                )
                if user_results is not None:
                    nested = (
                        user_results.get("result")
                        if isinstance(user_results.get("result"), dict)
                        else None
                    )
                    if nested is not None:
                        return nested
            return result
        return user
    return body


def _unwrap_tweet(body: dict[str, Any]) -> dict[str, Any]:
    for key in ("tweet", "tweet_results", "result", "tweetResult"):
        value = body.get(key)
        if isinstance(value, dict):
            if key == "tweet_results":
                nested = value.get("result")
                if isinstance(nested, dict):
                    return nested
            elif _tweet_external_id(value, None):
                return value
    if _tweet_external_id(body, None):
        return body
    for key in ("tweet", "tweet_results", "result"):
        value = body.get(key)
        if isinstance(value, dict):
            return value
    return body


def _graphql_tweet_entries(body: dict[str, Any]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    timeline_v2 = body.get("timeline_v2") if isinstance(body.get("timeline_v2"), dict) else None
    if timeline_v2 is None:
        return entries
    timeline = (
        timeline_v2.get("timeline") if isinstance(timeline_v2.get("timeline"), dict) else None
    )
    if timeline is None:
        return entries
    instructions = timeline.get("instructions")
    if not isinstance(instructions, list):
        return entries
    for instruction in instructions:
        if not isinstance(instruction, dict):
            continue
        if instruction.get("type") == "TimelineAddEntries":
            raw_entries = instruction.get("entries")
            if not isinstance(raw_entries, list):
                continue
            for entry in raw_entries:
                if not isinstance(entry, dict):
                    continue
                content = entry.get("content") if isinstance(entry.get("content"), dict) else None
                if content is None:
                    continue
                item = (
                    content.get("itemContent")
                    if isinstance(content.get("itemContent"), dict)
                    else None
                )
                if item is None:
                    item = content.get("tweet") if isinstance(content.get("tweet"), dict) else None
                if item is None:
                    continue
                result = (
                    item.get("tweet_results")
                    if isinstance(item.get("tweet_results"), dict)
                    else None
                )
                if result is not None:
                    nested = result.get("result")
                    if isinstance(nested, dict):
                        entries.append(nested)
                    continue
                if _tweet_external_id(item, None):
                    entries.append(item)
    return entries
